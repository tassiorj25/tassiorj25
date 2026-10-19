# Blueprint

Engenharia reversa de apps web públicos para **evidência medida**, e depois a
reconstrução — com portões que falham fechados em acessibilidade, paridade e
originalidade.

Sete skills de agente e sete ferramentas. Sem engines nativas, sem fork de
template, sem credenciais, sem crawler. Python stdlib mais Playwright.

> *Read in [English](README.md).*

## Por que isso existe

Fiz a varredura das skills de engenharia reversa em alta no GitHub —
[REA](https://github.com/morluto/rea) (333 mil estrelas),
[replica-skill](https://github.com/Jakeschincariol/replica-skill),
[ai-website-cloner-template](https://github.com/JCodesMore/ai-website-cloner-template),
[reverse-skill](https://github.com/zhaoxuya520/reverse-skill) — e cada uma tem
uma peça da resposta. A análise completa está em
[`docs/RESEARCH.md`](docs/RESEARCH.md).

- **REA** tem o rigor: Evidence IDs, observação separada de inferência, um
  registro de achados. Mas aponta para binários e precisa de Ghidra ou IDA.
- **replica-skill** tem o pipeline e a ética de sala limpa. Só que o recon lê
  documentação e páginas de marketing, então a construção fica a jusante de
  *inferência*.
- **ai-website-cloner** tem a ideia que mais importa — `getComputedStyle` em
  vez de "uns 14px, eu acho". Mas é só visual e não tem modelo de dados.

Ninguém havia combinado os três. Blueprint é essa combinação, apontada para o
alvo que a maioria realmente quer reconstruir: um app web público.

**A tese.** Clones saem errados porque um valor entra na construção como
chute e nada depois consegue perceber. Então:

1. **Medir, nunca chutar.** Se o navegador não reportou, não é um valor.
2. **Nada entra numa especificação sem um Evidence ID.** O ledger faz hash de
   cada captura bruta, então qualquer afirmação pode ser reconferida contra os
   bytes de origem.
3. **`observed`, `inferred` e `chosen` são palavras diferentes.** Divergir é o
   objetivo de uma reconstrução — mas nunca disfarçado de observação.
4. **Verificar com o mesmo instrumento.** Capture a sua própria build
   exatamente como capturou o alvo, e compare os dois sistemas derivados.
5. **Portões falham fechados.** Uma proteção que se ignora por padrão é
   decoração.

## Instalação

```bash
# como plugin do Claude Code
/plugin marketplace add tassiorj25/tassiorj25
/plugin install blueprint@blueprint

# ou copiando as skills
git clone https://github.com/tassiorj25/tassiorj25 blueprint
cp -r blueprint/skills/bp-* ~/.claude/skills/     # ou .claude/skills/ num projeto
```

Requisitos: Python 3.9+ (só stdlib), Node 18+, e Playwright para a captura.
Pillow é opcional, usado apenas pelo diff visual.

```bash
npm install playwright && npx playwright install chromium
```

## O pipeline

```
bp-recon  →  bp-tokens  →  bp-model  →  bp-spec  →  bp-build  →  bp-verify  →  bp-brand
 medir       sistema de    modelo de   especs      código      pontuar       portão
             design        dados       exatas                                de embarque
```

Cada etapa escreve em `blueprint/` no seu projeto e lê o que veio antes.
Qualquer etapa também roda sozinha.

| Skill | Faz | Escreve |
|---|---|---|
| `bp-recon` | captura evidência, mapeia telas e fluxos | `evidence/`, `recon.md`, `findings.md` |
| `bp-tokens` | agrupa estilos medidos em tokens; portão de contraste | `tokens.json`, `tokens.css` |
| `bp-model` | entidades por shapes de resposta, coleções pelo DOM | `model.json`, `model.md` |
| `bp-spec` | especificações com valores exatos e citações | `spec/*.md` |
| `bp-build` | constrói a partir das especs, com seu conteúdo | seu código, `divergences.md` |
| `bp-verify` | pontuação de paridade + diff visual, com portão | `parity.json`, `verify.md` |
| `bp-brand` | varredura de originalidade — falha fechado | `sweep.json`, `ship.md` |

## As ferramentas

Cada uma roda sozinha. `--help` em qualquer delas.

```bash
# medir uma página: estilos computados, caixas do DOM, shapes de resposta, assets
node tools/capture.mjs --out blueprint/evidence --viewports 390,1440 https://alvo.test/

# refaz o hash de cada arquivo bruto; falha se algum mudou depois da captura
python3 tools/ledger.py --dir blueprint/evidence verify

# agrupa o que foi medido num sistema de design
python3 tools/tokens.py --dir blueprint/evidence --out blueprint/tokens.json --css blueprint/tokens.css

# verificação WCAG sobre a paleta derivada
python3 tools/contrast.py --tokens blueprint/tokens.json --gate

# entidades, campos, relações, endpoints
python3 tools/model.py --dir blueprint/evidence --out blueprint/model.json

# pontua sua build contra o alvo, com evidência dos dois lados
python3 tools/parity.py --target blueprint/evidence --clone blueprint/clone-evidence --gate 80

# diff de pixels com heatmap e pontuação por faixa
python3 tools/imgdiff.py alvo.png clone.png --heatmap diff.png

# o portão de embarque: marca, domínio, cópia literal, URLs de asset
python3 tools/sweep.py --dir blueprint/evidence --source .
```

### Como é a saída

Contra o [news.ycombinator.com](https://news.ycombinator.com), uma página, um
viewport:

```
$ python3 tools/model.py --dir blueprint/evidence
  dom_collections_inferred: 10
  → tr.athing.submission   rows=30  uniform_w=1.0
      slot span.rank   x1 → label
      slot td.votelinks x1 → container
      slot a           x3 → link
```

Encontrou as 30 linhas de histórias e o que cada uma renderiza, sem nenhuma API
para ler.

```
$ python3 tools/contrast.py --tokens blueprint/tokens.json
   3.54  AA-large-only  #828282  on #f6f6ef  (x657)
```

Esse é um achado real de acessibilidade sobre o alvo real — exatamente o tipo
de coisa que você **não** quer herdar.

```
$ python3 tools/parity.py --target ... --clone ...
overall parity  63.44/100
  palette     91.32    type   67.90    spacing  35.20
  shape      100.00    structure  32.99
  unmatched spacing step 6px (used x30)
```

A quebra por dimensão é a parte útil: esse clone acertou as cores e errou a
grade.

## Limites

O `capture.mjs` aplica isto, em vez de apenas documentar:

- **robots.txt decide**, e um `Disallow` **não tem override**. Um `robots.txt`
  inacessível também recusa, em vez de assumir permissão.
- **Sem crawler.** Você passa a lista de páginas; `--max-pages` limita.
- **Sem credenciais.** Esse caminho de código não existe.
- **Shapes, não payloads.** Corpos JSON são reduzidos a esquemas de chave/tipo
  no navegador, antes de qualquer escrita, então dado real de usuário nunca
  chega ao disco.
- **Assets são inventariados, nunca baixados.**

E o `sweep.py` falha fechado na marca, domínio, cópia literal e URLs de asset
do alvo — inclusive uma marca quebrada em duas linhas e o aproveitamento
parcial de um parágrafo.

O que nenhuma ferramenta decide por você — termos de uso, trade dress, marca
registrada, licenças — está em [`docs/LEGAL.md`](docs/LEGAL.md). Uma varredura
limpa não é liberação jurídica.

## Testes

104 testes, sem rede, sem navegador, sem `pip install`.

```bash
python3 tests/run.py                      # 86 testes Python
node --test tests/capture-rules.test.mjs  # 18 testes Node
```

Cobrem o que apodreceria em silêncio: as razões WCAG contra os valores de
referência da própria especificação, detecção de adulteração no ledger,
precedência no robots.txt (incluindo exceções com `Allow` e grupos de agente
nomeados), que o `jsonShape` nunca emite um valor de payload, e que a paridade
reporta uma unidade-base divergente em vez de diluí-la na média.

## Licença

MIT. Veja [LICENSE](LICENSE).
