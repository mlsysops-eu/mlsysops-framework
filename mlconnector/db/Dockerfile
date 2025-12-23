FROM postgres:16-bookworm

ENV LANG=en_US.UTF-8 LANGUAGE=en_US:en LC_ALL=en_US.UTF-8

# Copy init assets. Number prefix enforces order if you have multiple files.
COPY configs/init-my-db.sh /docker-entrypoint-initdb.d/10-init-my-db.sh

# Normalize Windows line endings just in case (no harm if already LF)
RUN sed -i 's/\r$//' /docker-entrypoint-initdb.d/10-init-my-db.sh
