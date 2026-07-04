# LotsoNet

![lotsonet-logo](img/LotsoNet_logo.png)

## Resumo:

LotsoNet é um projeto de faculdade para a disciplina de Sistemas Distribuídos. Temos o intuito de construir uma rede P2P resiliente e descentralizada de Comando e Controle. 

## Como rodar:

Inicie um ambiente virtual:
```shell
python -m venv venv
```
Instale as dependências:
```shell
pip install -r requirements.txt
```

Em um dispositivo/terminal, incie o nó âncora:
```shell
python bootstrap.py
```

Em um dispositivo/terminal distintos inicie um nó:
```shell
python node.py 8469
```

