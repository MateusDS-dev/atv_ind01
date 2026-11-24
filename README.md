# Rota Vital · Função serverless (guia de transporte)

Atividade individual 1 · Infraestrutura de Software · ADS · CESAR School · 2026.2
Autor: Mateus Henrique Diniz Silva
Vídeo: <PREENCHER LINK DO VÍDEO>

Função serverless acionada por evento e por HTTP que recebe uma requisição do Rota Vital e devolve a guia de transporte.

## Caminho escolhido

**Caminho A: AWS SAM CLI local** (Docker + SAM CLI + Python 3.12), sem conta na AWS e sem publicar na nuvem.

## Estrutura

```
template.yaml          # API POST /guias, Timeout em Globals, 128 MB
hello_world/app.py     # handler (lê o body, gera a guia, contador global)
events/pedido.json     # evento no formato API Gateway proxy
evidencias/            # saídas dos comandos (.txt) e prints (.png)
README.md
.gitignore
```

## Como rodar

Pré-requisitos: Docker rodando, `sam --version` funcionando, Python 3.12. No Windows, usar Git Bash ou WSL. Todos os comandos são executados na raiz do repositório.

```bash
# 1. Build
sam build

# 2. Invocar com evento (rodar duas vezes e anotar o tempo)
sam local invoke -e events/pedido.json

# 3. Gatilho HTTP
sam local start-api
# em outro terminal, três vezes:
curl -X POST http://127.0.0.1:3000/guias -H "Content-Type: application/json" \
  -d '{"requisicaoId":"R-002","hospital":"H-Caruaru"}'

# 4. Reaproveitamento do ambiente
# parar o servidor (Ctrl+C) e subir de novo:
sam local start-api --warm-containers LAZY
# repetir os três curls

# 5. Limite de tempo (Timeout = 3 no template)
curl -X POST http://127.0.0.1:3000/guias -H "Content-Type: application/json" \
  -d '{"requisicaoId":"R-003","demorar":true}'
# depois: Timeout: 10 no template.yaml, sam build, repetir o curl
```

O evento `events/pedido.json` foi gerado com:

```bash
sam local generate-event apigateway aws-proxy --method POST --path guias \
  --body '{"requisicaoId":"R-001","hospital":"H-Recife","bolsas":["O-NEG-0142"]}' > events/pedido.json
```

## Evidências

A pasta `evidencias/` tem a saída dos comandos em `.txt` (`01-invoke-1.txt` a `07-erro-400.txt`) e os prints em `.png`:

`01-sam-version.png`, `02-invoke-1.png`, `03-invoke-2.png`, `04-start-api-curls.png`, `05-warm-containers.png`, `06-timeout-erro.png`, `07-timeout-10-ok.png`

## Resultados observados

| Experimento | Resultado |
|---|---|
| `sam local invoke` (1ª vez) | Duration: 59.87 ms · Init Duration: 0.05 ms · wall time: 45.78 s (inclui o download/build da imagem Docker) · `invocacaoNesteAmbiente`: 1 |
| `sam local invoke` (2ª vez) | Duration: 49.83 ms · Init Duration: 0.03 ms · wall time: 9.41 s (imagem já em cache) · `invocacaoNesteAmbiente`: 1 · outro `SAM_CONTAINER_ID` |
| `start-api` sem `--warm-containers`, 3 chamadas | `invocacaoNesteAmbiente`: 1, 1, 1 |
| `start-api --warm-containers LAZY`, 3 chamadas | `invocacaoNesteAmbiente`: 1, 2, 3 |
| `demorar: true` com Timeout 3 | HTTP 502 — `Function 'GuiaTransporteFunction' timed out after 3 seconds` |
| `demorar: true` com Timeout 10 | HTTP 201 — resposta em ~9.4 s (5 s de sleep + overhead do container) |
| body sem `requisicaoId` | HTTP 400 — `{"erro": "requisicaoId obrigatório"}` |

## Respostas

**1. Por que a primeira invocação demorou mais que a segunda? O que acontece na fase de Init?**
Na fase de Init a plataforma cria o ambiente de execução (no SAM local, sobe um container), inicia o runtime Python e executa o código que fica fora do handler (os imports e `contador = 0`). Só depois o handler roda. É isso que chamamos de cold start.
No `sam local invoke`, porém, cada chamada sobe um container novo. Nas minhas evidências, as duas invocações retornaram `invocacaoNesteAmbiente` = 1 e o `SAM_CONTAINER_ID` foi diferente, então as duas passaram pelo Init (as duas foram cold start). A diferença de tempo (wall time de 45.78 s contra 9.41 s) veio do download/build da imagem Docker, que só aconteceu na primeira vez, e não do ambiente ser reaproveitado. O Init Duration reportado ficou praticamente igual nas duas (0.05 ms e 0.03 ms). A diferença real entre cold e warm só aparece quando o ambiente é reaproveitado, como no `--warm-containers` (pergunta 2) e no Lambda na nuvem, onde o Init Duration é bem maior e visível nos logs.

**2. O que o campo `invocacaoNesteAmbiente` mostrou com e sem `--warm-containers`? O que isso diz sobre guardar estado numa variável global?**
Com o ambiente reaproveitado, o contador cresce (1, 2, 3). Quando o ambiente é recriado a cada chamada, ele volta a 1. Ou seja, a variável global só sobrevive enquanto o ambiente for reaproveitado, e a plataforma não garante isso. Estado que precisa persistir (ou ser compartilhado entre instâncias) deve ficar fora da função, em banco de dados, cache ou armazenamento externo. A variável global serve no máximo como cache descartável.
Observado na minha execução: sem `--warm-containers`, `invocacaoNesteAmbiente` foi 1, 1, 1 (container novo a cada chamada). Com `--warm-containers LAZY`, foi 1, 2, 3 (container reutilizado).

**3. O que aconteceu com `demorar = true`? Qual é o tempo máximo de uma execução no Lambda e o que fazer com um trabalho mais longo?**
A função dorme 5 s, mas o Timeout do template é 3 s, então a plataforma interrompe a execução e devolve erro de tempo limite. Com Timeout 10 ela termina e responde 201. O máximo no Lambda é 15 minutos (900 s); conferir em [Cotas do Lambda](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html). Trabalho mais longo deve ser quebrado em etapas menores (por exemplo, com filas e várias funções) ou ir para um serviço sem esse limite, como containers (ECS/Fargate) ou VMs.
Observado na minha execução: com Timeout 3, recebi HTTP 502 e o log do SAM mostrou `Function 'GuiaTransporteFunction' timed out after 3 seconds`. Após mudar para Timeout 10 e rodar `sam build`, a mesma chamada retornou HTTP 201 em ~9.4 s.

**4. Custo de 1 milhão de execuções com 128 MB e 100 ms (us-east-1)**

- Requisições: 1.000.000 × US$ 0,20 / 1.000.000 = **US$ 0,20**
- Computação: 128 MB = 0,125 GB; 100 ms = 0,1 s
  - GB-s = 1.000.000 × 0,125 × 0,1 = **12.500 GB-s**
  - 12.500 × US$ 0,0000166667 = **US$ 0,2083**
- **Total ≈ US$ 0,41** (0,20 + 0,2083 = 0,4083), antes da faixa gratuita.

**5. Em que parte do Rota Vital uma função assim faria sentido, e em qual não faria?**
Faz sentido em tarefas curtas, sem estado e acionadas por evento ou com demanda irregular: gerar a guia de transporte quando uma requisição é criada, validar o pedido, enviar notificações. Paga-se só quando há uso e escala sozinha em picos. Não faria sentido onde há conexão contínua ou estado em memória: rastreamento em tempo real de uma entrega (conexões abertas, atualizações frequentes), processamentos longos acima do limite de tempo, ou componentes que exigem latência previsível sem cold start. O banco de dados do sistema também não é um bom candidato.

## Uso de IA

- **Claude (Anthropic):** apoio para montar a estrutura do projeto SAM, o `template.yaml`, o rascunho do README e do roteiro do vídeo, e a revisão do repositório contra a rubrica da atividade.
- **Antigravity (Google DeepMind):** executou comandos (`sam build`, `sam local invoke`, `sam local start-api`, `curl`) e coletou as saídas em texto na pasta `evidencias/`.
- **Como validei:** <PREENCHER: o que EU executei e conferi pessoalmente, e como validei as respostas>
