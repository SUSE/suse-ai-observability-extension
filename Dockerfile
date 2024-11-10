FROM golang:1.23-alpine AS builder

WORKDIR /app

COPY go.mod go.sum ./

RUN go mod download

COPY . .

RUN go build -trimpath -o /app/openlitsync ./cmd/sync/main.go

FROM alpine:3.20.3

RUN apk --no-cache update && apk --no-cache add stress-ng

USER 1001
WORKDIR /app

COPY --from=builder /app/openlitsync .

CMD ["/app/openlitsync"]
