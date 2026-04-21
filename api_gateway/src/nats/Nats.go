package nats

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/nats-io/nats.go"
	"github.com/nats-io/nats.go/jetstream"
	"time"
)

type NatsContext struct {
	NatsCore           *nats.Conn
	NatsJetStream      jetstream.JetStream
	asyncRequestTopic  string
	asyncResponseTopic string
}

func NewNatsConn(
	url string,
	asyncRequestTopic string,
	asyncResponseTopic string,
) (*NatsContext, error) {
	conn, err := nats.Connect(url)

	if err != nil {
		return nil, err
	}

	jsCtx, err := jetstream.New(conn)

	if err != nil {
		return nil, err
	}

	nc := &NatsContext{
		NatsCore:           conn,
		NatsJetStream:      jsCtx,
		asyncRequestTopic:  asyncRequestTopic,
		asyncResponseTopic: asyncResponseTopic,
	}

	return nc, nil
}

func (nc *NatsContext) Subscribe(
	ctx context.Context,
	asyncResponseHanlder func(jetstream.Msg),
) error {
	stream, err := nc.NatsJetStream.CreateOrUpdateStream(ctx, jetstream.StreamConfig{
		Name:     "STREAM_TRANSCRIBER_ASYNC_RESPONSE",
		Subjects: []string{nc.asyncResponseTopic},
	})

	if err != nil {
		return err
	}

	fmt.Println("subscribed")

	consumer, err := stream.CreateOrUpdateConsumer(ctx, jetstream.ConsumerConfig{
		Durable:   "api-gateway",
		AckPolicy: jetstream.AckExplicitPolicy,
	})

	if err != nil {
		return err
	}

	consumer.Consume(asyncResponseHanlder)

	return nil
}

func (nc *NatsContext) Close() {
	nc.NatsCore.Close()
}

func (nc *NatsContext) CreateAsyncJobFile(ctx context.Context, jobId string, file string) error {
	body := map[string]any{
		"job_id":     jobId,
		"input_type": "file",
		"created_at": time.Now().Format(time.RFC3339),
		"audio_source": map[string]any{
			"path": file,
		},
	}

	jsonContent, err := json.Marshal(body)

	if err != nil {
		return err
	}

	_, err = nc.NatsJetStream.Publish(ctx, nc.asyncRequestTopic, jsonContent)

	if err != nil {
		return err
	}

	return nil
}
