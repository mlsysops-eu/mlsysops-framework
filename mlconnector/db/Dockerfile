FROM harbor.nbfc.io/proxy_cache/library/postgres
USER root
RUN export LANGUAGE=en_US.UTF-8
COPY configs/init-my-db.sh /docker-entrypoint-initdb.d/init-user-db.sh
# COPY configs/drift_metrics_mmd.csv /docker-entrypoint-initdb.d/drift_metrics_mmd.csv
