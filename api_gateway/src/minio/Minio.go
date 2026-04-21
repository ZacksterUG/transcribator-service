package minio

import (
	"context"
	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"io"
	"strings"
)

type MinIOClient struct {
	minioClient   *minio.Client
	defaultBucket string
}

func NewMinIOClient(host, login, password, defaultBucket string) (*MinIOClient, error) {
	validHost := strings.Split(host, "://")[1]

	options := &minio.Options{
		Creds:  credentials.NewStaticV4(login, password, ""),
		Secure: false,
	}

	client, err := minio.New(validHost, options)

	if err != nil {
		return nil, err
	}

	exists, err := client.BucketExists(context.Background(), defaultBucket)

	if err != nil {
		return nil, err
	}

	if !exists {
		client.MakeBucket(context.Background(), defaultBucket, minio.MakeBucketOptions{})
	}

	c := &MinIOClient{
		minioClient:   client,
		defaultBucket: defaultBucket,
	}

	return c, nil
}

func (c *MinIOClient) GetDefaultBucket() string {
	return c.defaultBucket
}

// Put загружает данные в объект. size = -1 для потоковой загрузки.
func (c *MinIOClient) Put(ctx context.Context, objectName string, reader io.Reader, size int64, contentType string) error {
	opts := minio.PutObjectOptions{ContentType: contentType}
	_, err := c.minioClient.PutObject(ctx, c.defaultBucket, objectName, reader, size, opts)
	return err
}

// Get возвращает читатель для объекта. Не забудьте закрыть io.ReadCloser.
func (c *MinIOClient) Get(ctx context.Context, objectName string) (io.ReadCloser, error) {
	return c.minioClient.GetObject(ctx, c.defaultBucket, objectName, minio.GetObjectOptions{})
}

// Delete удаляет объект.
func (c *MinIOClient) Delete(ctx context.Context, objectName string) error {
	return c.minioClient.RemoveObject(ctx, c.defaultBucket, objectName, minio.RemoveObjectOptions{})
}

// Exists проверяет существование объекта.
func (c *MinIOClient) Exists(ctx context.Context, objectName string) (bool, error) {
	_, err := c.minioClient.StatObject(ctx, c.defaultBucket, objectName, minio.StatObjectOptions{})
	if err != nil {
		if minio.ToErrorResponse(err).Code == "NoSuchKey" {
			return false, nil
		}
		return false, err
	}
	return true, nil
}

// List возвращает канал с информацией об объектах. Закройте канал после чтения.
func (c *MinIOClient) List(ctx context.Context, prefix string, recursive bool) <-chan minio.ObjectInfo {
	ch := make(chan minio.ObjectInfo)
	go func() {
		defer close(ch)
		for obj := range c.minioClient.ListObjects(ctx, c.defaultBucket, minio.ListObjectsOptions{
			Prefix:    prefix,
			Recursive: recursive,
		}) {
			if obj.Err != nil {
				// Опционально: логировать ошибку
				continue
			}
			ch <- obj
		}
	}()
	return ch
}

// FolderExists проверяет, есть ли объекты с указанным префиксом (папкой).
// folderPath можно передавать как "my-folder", "my-folder/" или "path/to/folder" — метод нормализует.
func (c *MinIOClient) FolderExists(ctx context.Context, folderPath string) (bool, error) {
	// Нормализация: добавляем завершающий слэш, если нет
	if !strings.HasSuffix(folderPath, "/") {
		folderPath += "/"
	}

	// Ищем хотя бы один объект с этим префиксом (не рекурсивно, только 1 результат)
	opts := minio.ListObjectsOptions{
		Prefix:    folderPath,
		Recursive: false,
		MaxKeys:   1,
	}

	for obj := range c.minioClient.ListObjects(ctx, c.defaultBucket, opts) {
		if obj.Err != nil {
			return false, obj.Err
		}
		// Нашли хотя бы один объект → папка «существует»
		return true, nil
	}

	// Ничего не найдено
	return false, nil
}

func (c *MinIOClient) GetBytes(ctx context.Context, objectName string) ([]byte, error) {
	reader, err := c.minioClient.GetObject(ctx, c.defaultBucket, objectName, minio.GetObjectOptions{})
	if err != nil {
		return nil, err
	}
	defer reader.Close() // 🔥 Обязательно закрываем поток

	// Считываем всё содержимое в память
	data, err := io.ReadAll(reader)
	if err != nil {
		return nil, err
	}

	return data, nil
}
