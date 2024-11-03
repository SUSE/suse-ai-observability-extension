FROM golang:1.23-alpine AS builder

WORKDIR /app

COPY go.mod go.sum ./

RUN go mod download

COPY . .

RUN go build -trimpath -o /app/k8sync ./cmd/sync/main.go

FROM alpine:3.20.3

RUN apk --no-cache update && apk --no-cache add stress-ng

USER 1001
WORKDIR /app

COPY --from=builder /app/k8sync .

CMD ["/app/k8sync"]
