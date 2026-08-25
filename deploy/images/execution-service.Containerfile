FROM rust:1.88-bookworm AS build

WORKDIR /build
COPY Cargo.toml Cargo.lock ./
COPY packages/rust/noosfera-capability packages/rust/noosfera-capability
COPY packages/rust/noosfera-execution-kernel packages/rust/noosfera-execution-kernel
COPY packages/rust/noosfera-execution-service packages/rust/noosfera-execution-service
RUN cargo build --locked --release -p noosfera-execution-service

FROM debian:bookworm-slim AS runtime
RUN useradd --system --no-create-home --shell /usr/sbin/nologin noosfera
COPY --from=build /build/target/release/noosfera-execution-service /usr/local/bin/noosfera-execution-service
USER noosfera
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/noosfera-execution-service"]
