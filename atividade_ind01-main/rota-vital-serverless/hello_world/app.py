import json
import time

# Variável global: só sobrevive se o ambiente de execução for reaproveitado
# (warm start). Em um cold start ela volta a 0.
contador = 0


def lambda_handler(event, context):
    global contador
    contador += 1

    pedido = json.loads(event.get("body") or "{}")

    if "requisicaoId" not in pedido:
        return {
            "statusCode": 400,
            "body": json.dumps({"erro": "requisicaoId obrigatório"}),
        }

    if pedido.get("demorar"):
        time.sleep(5)  # passa do Timeout de 3 s do template

    guia = {
        "guia": "G-" + pedido["requisicaoId"],
        "hospital": pedido.get("hospital"),
        "bolsas": pedido.get("bolsas", []),
        "invocacaoNesteAmbiente": contador,
    }
    return {"statusCode": 201, "body": json.dumps(guia)}
