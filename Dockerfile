FROM python:3.9

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt 

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt 

COPY ./perp /code/perp 
COPY ./run.py /code/run.py 
COPY ./wallets_configs /code/wallets_configs
COPY ./wallets_encoded /code/wallets_encoded
COPY ./coins.json /code/coins.json
COPY ./fills /code/fills 
COPY ./logs /code/logs
CMD ["python", "run.py"]