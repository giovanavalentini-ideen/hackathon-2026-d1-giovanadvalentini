FROM golang:1.25-alpine AS build
WORKDIR /src
COPY go.mod *.go ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /motor .

FROM scratch
COPY --from=build /motor /app/motor
COPY regras/ /app/regras/
USER 65534:65534
ENTRYPOINT ["/app/motor"]
