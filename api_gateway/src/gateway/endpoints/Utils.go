package endpoints

import (
	"fmt"
	"github.com/gabriel-vasile/mimetype"
	"github.com/gin-gonic/gin"
	"io"
	"mime/multipart"
	"strings"
	"transcriber-api-gateway/src/gateway"
)

func RegisterRoutes(ctx *gateway.Context) {
	utilGroup := ctx.Group.Group("/")
	{
		utilGroup.GET("/heartbeat", heartbeat(ctx))
	}
}

func heartbeat(apiCtx *gateway.Context) gin.HandlerFunc {
	return func(c *gin.Context) {
		apiCtx.Logger.Printf("heartbeat ok!")

		c.JSON(200, gin.H{
			"message": "healthy",
		})
	}
}

func SendErrorMessage(c *gin.Context, status int, message string) {
	c.JSON(status, gin.H{
		"error":   true,
		"message": message,
	})
}

func DetectAudioType(file multipart.File, allowed []string) (string, error) {
	// 1. Детектим тип (прочитает ~1-4 КБ)
	mtype, err := mimetype.DetectReader(file)
	if err != nil {
		return "", err
	}

	// 2. Парсим тип (убираем параметры типа ; charset=...)
	detected := strings.Split(mtype.String(), ";")[0]

	// 3. Валидируем
	valid := false
	for _, a := range allowed {
		if detected == a {
			valid = true
			break
		}
	}
	if !valid {
		return "", fmt.Errorf("unsupported type: %s", detected)
	}

	// 4. Возвращаем файл в начало (multipart.File — это ReadSeeker)
	_, err = file.Seek(0, io.SeekStart)
	if err != nil {
		return "", err
	}

	return detected, nil
}
