# Keycloak Authentication Examples for Gin

This document provides example implementations showing how to use Keycloak authentication and authorization with the Gin web framework.

## Copy-Paste Examples

### Basic Setup

Create a new file for your endpoints and copy this template:

```go
// endpoints.go
package main

import (
    "net/http"
    
    "github.com/gin-gonic/gin"
    "transcriber-api-gateway/src/api/middleware/authorization"
)

// RegisterRoutes registers your application routes with auth middleware
func RegisterRoutes(r *gin.RouterGroup, auth *authorization.AuthHandler) {
    // Public endpoint - any authenticated user
    r.GET("/profile", auth.RequireAuth(), ProfileHandler)
    
    // Protected by role
    r.GET("/transcribator", 
        auth.RequireAuth(),
        auth.RequireRole("transcribator"),
        TranscribatorHandler,
    )
    
    // Multiple roles (OR)
    r.GET("/admin", 
        auth.RequireAuth(),
        auth.RequireAnyOfRoles("admin", "moderator"),
        AdminHandler,
    )
}

// ProfileHandler returns current user info
func ProfileHandler(c *gin.Context) {
    userID := authorization.GetUserIDFromContext(c)
    claims := authorization.GetClaimsFromContext(c)
    
    c.JSON(http.StatusOK, gin.H{
        "user_id": userID,
        "email": claims.Email,
        "username": claims.PreferredUsername,
        "realm_roles": claims.RealmAccess.Roles,
    })
}

// TranscribatorHandler protected by transcribator role
func TranscribatorHandler(c *gin.Context) {
    userID := authorization.GetUserIDFromContext(c)
    
    c.JSON(http.StatusOK, gin.H{
        "status": "authorized",
        "message": "You have the transcribator role",
        "user_id": userID,
    })
}

// AdminHandler protected by admin/moderator role
func AdminHandler(c *gin.Context) {
    userID := authorization.GetUserIDFromContext(c)
    
    c.JSON(http.StatusOK, gin.H{
        "status": "authorized",
        "user_id": userID,
    })
}
```

### Full Application Setup

```go
// main.go
package main

import (
    "log"
    "os"
    
    "github.com/gin-gonic/gin"
    "github.com/joho/godotenv"
    "transcriber-api-gateway/src/api/middleware/authorization"
)

func main() {
    // Load env
    godotenv.Load()
    
    // Configure Keycloak
    authConfig := authorization.AuthConfig{
        Type: authorization.AuthTypeKeycloak,
        KeycloakConfig: &authorization.KeycloakConfig{
            ServerURL:    getEnv("KEYCLOAK_URL", "http://localhost:8080"),
            Realm:        getEnv("KEYCLOAK_REALM", "master"),
            ClientID:     getEnv("KEYCLOAK_CLIENT_ID", "gateway-gateway"),
            ClientSecret: getEnv("KEYCLOAK_CLIENT_SECRET", ""),
            VerifySSL:    getEnvBool("KEYCLOAK_VERIFY_SSL", true),
        },
    }
    
    // Create authorizer
    authorizer, err := authorization.CreateAuthorizer(authConfig)
    if err != nil {
        log.Fatal("Failed to create authorizer:", err)
    }
    
    authHandler := authorization.NewAuthHandler(authorizer)
    
    // Setup Gin
    r := gin.Default()
    
    api := r.Group("/gateway")
    {
        RegisterRoutes(api, authHandler)
    }
    
    port := getEnv("PORT", "8080")
    log.Printf("Server starting on :%s", port)
    r.Run(":" + port)
}

func getEnv(key, fallback string) string {
    if value := os.Getenv(key); value != "" {
        return value
    }
    return fallback
}

func getEnvBool(key string, fallback bool) bool {
    if value := os.Getenv(key); value == "true" {
        return true
    } else if value == "false" {
        return false
    }
    return fallback
}
```

## Available Middleware

| Middleware | Description |
|------------|-------------|
| `auth.RequireAuth()` | Validates JWT token, extracts claims |
| `auth.RequireRole("role")` | Requires specific role (realm or client) |
| `auth.RequireAnyOfRoles("a", "b")` | Requires any of the roles |
| `auth.RequireAllRoles("a", "b")` | Requires all of the roles |

## Accessing User Data

```go
func MyHandler(c *gin.Context) {
    // User ID (sub from JWT)
    userID := authorization.GetUserIDFromContext(c)
    
    // Full claims
    claims := authorization.GetClaimsFromContext(c)
    
    // Access specific fields
    email := claims.Email
    username := claims.PreferredUsername
    realmRoles := claims.RealmAccess.Roles
    clientRoles := claims.ResourceAccess["your-client"].Roles
}
```

## Expected JWT Structure

```json
{
    "sub": "ff4bc721-91e6-4651-9c3e-3de0fc58bcbb",
    "email": "user@example.com",
    "preferred_username": "johndoe",
    "realm_access": {
        "roles": ["user", "transcribator", "admin"]
    },
    "resource_access": {
        "my-client": {
            "roles": ["client-role"]
        }
    }
}
```

## Testing with curl

```bash
# Get token
TOKEN=$(curl -s -X POST \
    http://localhost:8080/realms/my-realm/protocol/openid-connect/token \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=password" \
    -d "client_id=my-client" \
    -d "username=user" \
    -d "password=pass" \
    | jq -r '.access_token')

# Test endpoint
curl -H "Authorization: Bearer $TOKEN" \
    http://localhost:8080/api/profile

# Test protected endpoint
curl -H "Authorization: Bearer $TOKEN" \
    http://localhost:8080/api/transcribator
```

## Response Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 401 | Unauthorized - missing/invalid token |
| 403 | Forbidden - valid token, insufficient roles |
| 503 | Keycloak unavailable |

## Environment Variables

```bash
KEYCLOAK_URL=http://localhost:8080
KEYCLOAK_REALM=my-realm
KEYCLOAK_CLIENT_ID=gateway-gateway
KEYCLOAK_CLIENT_SECRET=optional-secret
KEYCLOAK_VERIFY_SSL=true
```

## Dependencies

```go
require (
    github.com/gin-gonic/gin
    github.com/Nerzal/gocloak/v12
    github.com/wirnat/go-keycloak-middleware
)
```
