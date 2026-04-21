package interfaces

import (
	"log"
)

type StdLogger struct {
	logger *log.Logger
}

func NewStdLogger(l *log.Logger) *StdLogger {
	return &StdLogger{logger: l}
}

func (l *StdLogger) Printf(format string, v ...interface{}) {
	l.logger.Printf(format, v...)
}

func (l *StdLogger) Print(v ...interface{}) {
	l.logger.Print(v...)
}
