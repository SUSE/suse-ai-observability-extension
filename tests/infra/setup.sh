#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting StackState and OTel Collector...${NC}"
docker-compose up -d

echo -e "${YELLOW}Waiting for StackState to become healthy...${NC}"
MAX_ATTEMPTS=60
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if curl -f -s http://localhost:7070/api/server/info > /dev/null 2>&1; then
        echo -e "${GREEN}StackState is healthy!${NC}"
        break
    fi

    ATTEMPT=$((ATTEMPT + 1))
    echo -n "."
    sleep 5
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo -e "${RED}StackState failed to become healthy after $((MAX_ATTEMPTS * 5)) seconds${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Infrastructure is ready!${NC}"
echo ""
echo "Export these environment variables to run integration tests:"
echo ""
echo "export STACKSTATE_API_URL=http://localhost:7070"
echo "export STACKSTATE_API_TOKEN=\${YOUR_API_TOKEN}"
echo "export STACKSTATE_TOKEN_TYPE=Bearer"
echo "export STACKSTATE_SKIP_TLS=true"
echo "export OTEL_ENDPOINT=http://localhost:4318"
echo ""
echo "Run tests with: go test -tags=integration ./integration/..."
