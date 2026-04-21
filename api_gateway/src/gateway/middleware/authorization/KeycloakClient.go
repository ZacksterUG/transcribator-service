package authorization

import (
	"context"
	"fmt"
	"strings"

	"github.com/Nerzal/gocloak/v12"
	"github.com/golang-jwt/jwt/v5"
	"transcriber-api-gateway/src/gateway/interfaces"
)

// KeycloakConfig конфигурация для Keycloak
type KeycloakConfig struct {
	ServerURL    string
	Realm        string
	ClientID     string
	ClientSecret string
	VerifySSL    bool
	Logger       interfaces.Logger
}

// KeycloakClient обертка над gocloak клиентом
type KeycloakClient struct {
	client    *gocloak.GoCloak
	config    KeycloakConfig
	logger    interfaces.Logger
	issuerURL string
}

// KeycloakUserInfo информация о пользователе из Keycloak
type KeycloakUserInfo struct {
	Sub               string   `json:"sub"`
	Email             string   `json:"email"`
	EmailVerified     bool     `json:"email_verified"`
	Name              string   `json:"name"`
	PreferredUsername string   `json:"preferred_username"`
	Roles             []string `json:"roles"`
}

// TokenClaims расширенные claims токена
type TokenClaims struct {
	jwt.RegisteredClaims
	RealmAccess       RealmAccess               `json:"realm_access"`
	ResourceAccess    map[string]ResourceAccess `json:"resource_access"`
	Email             string                    `json:"email"`
	Name              string                    `json:"name"`
	PreferredUsername string                    `json:"preferred_username"`
}

// RealmAccess структура для realm ролей
type RealmAccess struct {
	Roles []string `json:"roles"`
}

// ResourceAccess структура для ресурсных ролей
type ResourceAccess struct {
	Roles []string `json:"roles"`
}

// NewKeycloakClient создает новый клиент Keycloak
func NewKeycloakClient(config KeycloakConfig) *KeycloakClient {
	client := gocloak.NewClient(config.ServerURL)

	logger := config.Logger
	if logger == nil {
		logger = interfaces.NewStdLogger(nil)
	}

	return &KeycloakClient{
		client:    client,
		config:    config,
		logger:    logger,
		issuerURL: fmt.Sprintf("%s/realms/%s", strings.TrimSuffix(config.ServerURL, "/"), config.Realm),
	}
}

// GetGocloakClient возвращает gocloak клиент для middleware
func (kc *KeycloakClient) GetGocloakClient() *gocloak.GoCloak {
	return kc.client
}

// GetConfig возвращает конфигурацию
func (kc *KeycloakClient) GetConfig() KeycloakConfig {
	return kc.config
}

// ValidateToken валидирует JWT токен
func (kc *KeycloakClient) ValidateToken(tokenString string) (*TokenClaims, error) {
	ctx := context.Background()

	// Декодируем токен без валидации для получения claims
	_, claimsMap, err := kc.client.DecodeAccessToken(ctx, tokenString, kc.config.Realm)
	if err != nil {
		kc.logger.Printf("[Keycloak] Token decode failed: %v", err)
		return nil, fmt.Errorf("failed to decode token: %w", err)
	}

	// Преобразуем claims в структуру
	claims := &TokenClaims{}

	if sub, ok := (*claimsMap)["sub"].(string); ok {
		claims.Subject = sub
	}
	if iss, ok := (*claimsMap)["iss"].(string); ok {
		claims.Issuer = iss
	}
	if email, ok := (*claimsMap)["email"].(string); ok {
		claims.Email = email
	}
	if name, ok := (*claimsMap)["name"].(string); ok {
		claims.Name = name
	}
	if preferredUsername, ok := (*claimsMap)["preferred_username"].(string); ok {
		claims.PreferredUsername = preferredUsername
	}

	// realm_access
	if realmAccess, ok := (*claimsMap)["realm_access"].(map[string]interface{}); ok {
		if roles, ok := realmAccess["roles"].([]interface{}); ok {
			for _, r := range roles {
				if roleStr, ok := r.(string); ok {
					claims.RealmAccess.Roles = append(claims.RealmAccess.Roles, roleStr)
				}
			}
		}
	}

	// resource_access
	if resourceAccess, ok := (*claimsMap)["resource_access"].(map[string]interface{}); ok {
		claims.ResourceAccess = make(map[string]ResourceAccess)
		for clientID, clientRoles := range resourceAccess {
			if rolesMap, ok := clientRoles.(map[string]interface{}); ok {
				if roles, ok := rolesMap["roles"].([]interface{}); ok {
					var roleStrings []string
					for _, r := range roles {
						if roleStr, ok := r.(string); ok {
							roleStrings = append(roleStrings, roleStr)
						}
					}
					claims.ResourceAccess[clientID] = ResourceAccess{Roles: roleStrings}
				}
			}
		}
	}

	// Проверка issuer
	if claims.Issuer != kc.issuerURL {
		kc.logger.Printf("[Keycloak] Invalid issuer: expected %s, got %s", kc.issuerURL, claims.Issuer)
		return nil, fmt.Errorf("invalid issuer")
	}

	kc.logger.Printf("[Keycloak] Token validated for subject: %s", claims.Subject)
	return claims, nil
}

// HasRole проверяет наличие роли у пользователя
func (kc *KeycloakClient) HasRole(claims *TokenClaims, role string) bool {
	// Проверяем realm roles
	for _, r := range claims.RealmAccess.Roles {
		if r == role {
			return true
		}
	}

	// Проверяем client-specific roles
	for clientID, access := range claims.ResourceAccess {
		// Проверяем для текущего клиента
		if clientID == kc.config.ClientID {
			for _, r := range access.Roles {
				if r == role {
					return true
				}
			}
		}
	}

	return false
}

// GetUserInfo получает информацию о пользователе из Keycloak
func (kc *KeycloakClient) GetUserInfo(tokenString string) (*KeycloakUserInfo, error) {
	ctx := context.Background()

	userInfo, err := kc.client.GetUserInfo(ctx, tokenString, kc.config.Realm)
	if err != nil {
		return nil, fmt.Errorf("failed to get userinfo: %w", err)
	}

	info := &KeycloakUserInfo{
		Sub:               *userInfo.Sub,
		Email:             *userInfo.Email,
		Name:              *userInfo.Name,
		PreferredUsername: *userInfo.PreferredUsername,
	}

	return info, nil
}

// IsAvailable проверяет доступность Keycloak сервера
func (kc *KeycloakClient) IsAvailable() bool {
	ctx := context.Background()
	// Пробуем получить сертификаты для проверки доступности
	_, err := kc.client.GetCerts(ctx, kc.config.Realm)
	if err != nil {
		kc.logger.Printf("[Keycloak] Server unavailable: %v", err)
		return false
	}
	return true
}

// Logger возвращает логгер
func (kc *KeycloakClient) Logger() interfaces.Logger {
	return kc.logger
}

// RetrospectToken интроспекция токена (проверка активности)
func (kc *KeycloakClient) RetrospectToken(tokenString string) (*gocloak.IntroSpectTokenResult, error) {
	ctx := context.Background()
	return kc.client.RetrospectToken(ctx, tokenString, kc.config.ClientID, kc.config.ClientSecret, kc.config.Realm)
}
