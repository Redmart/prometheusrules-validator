FROM quay.io/prometheus/prometheus:v2.6.1 as prometheus

FROM python:3.7.2-stretch as final

RUN pip install kubernetes

COPY prometheusrules-validator.py .

COPY --from=prometheus /bin/promtool /bin

CMD [ "python", "./prometheusrules-validator.py" ]