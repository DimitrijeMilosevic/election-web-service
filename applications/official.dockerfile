FROM python:3

RUN mkdir -p /opt/src/applications
WORKDIR /opt/src/applications

COPY ./official.py ./application.py
COPY ./configuration.py ./configuration.py
COPY ./models.py ./models.py
COPY ./requirements.txt ./requirements.txt
COPY ./roleCheckDecorator.py ./roleCheckDecorator.py

RUN pip install -r ./requirements.txt

ENV PYTHONPATH="/opt/src/applications"

ENTRYPOINT ["python", "./application.py"]