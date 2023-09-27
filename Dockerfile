FROM python:3

RUN mkdir -p metrics/

RUN mkdir -p graphs/

RUN pip install boto3 requests matplotlib python-dotenv

COPY main.py /

COPY infrastructure_builder.py /

COPY metric_data.py /

COPY cloudwatch_monitor.py /

COPY workloads.py /

COPY .env /

COPY flask_setup_cluster1.sh /

COPY flask_setup_cluster2.sh /

CMD [ "python", "./main.py" ]