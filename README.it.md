# Estensione DMSF per Redmine AI Helper

Plugin Redmine separato che aggiunge **ricerca e analisi in sola lettura dei
documenti DMSF** alla chat di AI Helper.

[English documentation](README.md) · [Compatibilità](docs/compatibility.md) ·
[Test](docs/testing.md) · [Licenze e provenienza](THIRD_PARTY_NOTICES.md)

Versione **0.1.0**. Licenza **GPL-3.0-or-later**, con conservazione degli avvisi
MIT originali per il codice adattato da AI Helper.

## Cosa significa l'esempio `redmine_fortune`

L'esempio ufficiale
[`example/redmine_fortune/`](https://github.com/haru/redmine_ai_helper/tree/10362446a2eefd814ae76c6ec23094bddfc3cfe6/example/redmine_fortune)
mostra un plugin Redmine autonomo che registra un proprio agente e i suoi
strumenti. AI Helper riconosce automaticamente gli agenti che ereditano da
`RedmineAiHelper::BaseAgent`.

Questa estensione applica quel meccanismo a DMSF: si installa accanto a
`redmine_ai_helper` e `redmine_dmsf`, senza modificare i loro file. La
manutenzione delle chiamate alle API di DMSF rimane in questo repository.

## Funzionalità

- Ricerca per nome file, titolo e descrizione della revisione corrente.
- Inclusione facoltativa dei candidati trovati dalla ricerca Xapian di DMSF.
- Analisi della revisione corrente di PDF e file di testo/codice UTF-8 tramite
  il modello già configurato in AI Helper.
- Risposte con URL originale DMSF, versione e ID della revisione.
- Controlli sugli accessi di AI Helper, sui permessi DMSF del progetto, sulle
  restrizioni delle cartelle e sulla visibilità della revisione.

Non sono previsti strumenti per creare, modificare, spostare, approvare o
cancellare documenti. L'estensione non aggiunge tabelle, migrazioni, indici,
schermate o servizi MCP esterni.

## Requisiti

| Componente | Versione o condizione |
| --- | --- |
| AI Helper | Almeno 3.13.0; è la versione delle API esaminata |
| DMSF | Almeno 5.0.0, con Active Storage |
| Redmine | Almeno 6.1 per DMSF 5.0.x; almeno 7.0 per DMSF 5.1.x/5.2.x |
| Ruby | Compatibile con Redmine e AI Helper; la base di AI Helper richiede 3.2+ |
| Modello AI | Deve supportare il tipo di allegato da analizzare |

Le API sono state verificate nel codice delle versioni DMSF 5.0.0, 5.0.5,
5.1.1 e 5.2.0. Questa verifica del sorgente **non equivale a un collaudo
completo delle diverse installazioni**. DMSF 4.x non è supportato perché usa
API di archiviazione differenti. Dettagli nella [matrice di compatibilità](docs/compatibility.md).

## Installazione

1. Installa e configura Redmine, AI Helper e DMSF nelle rispettive versioni
   compatibili. Verifica prima che chat e gestione documenti funzionino.
2. Dalla **directory principale di Redmine** esegui:

   ```bash
   git clone https://github.com/p4535992/redmine_ai_helper_extension_dmfs.git plugins/redmine_ai_helper_extension_dmfs
   ```

3. Configura nell'ambiente dei processi Redmine:

   ```bash
   REDMINE_AI_HELPER_DMSF_ENABLED=1
   ```

   Inseriscila nella configurazione del servizio o del container. Impostarla
   in una shell separata non modifica l'ambiente di un servizio già avviato.
4. In **Amministrazione → AI Helper** abilita **Send attachments to LLM** e
   imposta la dimensione massima degli allegati. Entrambe le attivazioni sono
   necessarie, anche per la ricerca dei metadati.
5. Abilita **DMSF** nei progetti interessati. I progetti devono essere
   accessibili anche secondo le regole di AI Helper e l'eventuale impostazione
   **Target all projects**.
6. Assegna agli utenti il permesso `view_dmsf_files`. Per l'analisi serve anche
   `view_dmsf_file_revisions`. Le restrizioni delle cartelle restano applicate.
7. Riavvia Redmine. In **Amministrazione → Plugin** deve comparire
   **Redmine AI Helper DMSF Extension**. Esegui i [test indicati](docs/testing.md)
   su un'installazione di prova prima di usarla con documenti reali.

Mantieni esattamente il nome della directory **`redmine_ai_helper_extension_dmfs`**:
`dmfs` rispetta il nome del repository esistente. Nel codice e nel nome del
prodotto viene usata la sigla corretta **DMSF**. Il nome della directory garantisce
anche il caricamento dopo AI Helper.

L'estensione non richiede gem aggiuntive o proprie migrazioni. Le dipendenze
richiedono comunque la loro normale procedura d'installazione.

Se usavi il branch sperimentale di AI Helper con DMSF incorporato, passa a una
versione compatibile di AI Helper senza quella integrazione incorporata. Il
nuovo agente ha un nome distinto, ma mantenere attive entrambe le integrazioni
farebbe comparire due agenti DMSF.

## Esempi di utilizzo

Nella normale chat AI Helper puoi chiedere:

- «Trova i documenti DMSF sulla specifica delle API nel progetto 12».
- «Riassumi il documento DMSF 42 e indica il collegamento originale e la versione».
- «La revisione corrente del documento DMSF 42 descrive i tempi di conservazione?».

Gli strumenti disponibili sono `search_files(query:, project_id: nil, limit: 10)`
e `analyze_file(file_id:, question: nil)`. La ricerca accetta fino a 200
caratteri; la domanda per l'analisi fino a 2.000.

L'agente rimane disabilitato quando manca DMSF, la sua API non è supportata o
uno dei due consensi amministrativi è spento. Anche le chiamate dirette agli
strumenti ricontrollano le condizioni d'accesso.

## Limiti da conoscere

**Formati:** PDF e testo/codice UTF-8 con estensioni `.txt`, `.md`, `.csv`,
`.json`, `.xml`, `.log`, `.rb`, `.py`, `.js`, `.html`, `.css`. Questa versione
non analizza documenti Office o revisioni storiche.

**Invio al modello:** l'analisi invia il contenuto del documento al fornitore AI
configurato. La dimensione viene verificata prima del download e nuovamente sui
byte effettivi prima dell'invio. All'agente non vengono restituiti percorsi
interni, chiavi di archiviazione o URL firmati dei blob.

**Ricerca limitata:** il primo passaggio esamina al massimo 2.000 documenti
candidati e restituisce al massimo 20 risultati autorizzati. La ricerca DMSF
facoltativa ha un limite separato di 2.000 candidati; Xapian ha ulteriori limiti
interni. `truncated: true` indica un limite incontrato dall'estensione.

**Revisioni:** la ricerca nell'indice può trovare corrispondenze nelle revisioni
precedenti. Il campo `match_source` distingue `current_metadata` da
`dmsf_search`. Un risultato proveniente dall'indice non dimostra che la revisione
corrente contenga quella frase: usa l'analisi per verificarlo. Metadati
restituiti e contenuto analizzato si riferiscono alla revisione attiva corrente.

**Indice:** `content_search: attempted` significa che è stata invocata la ricerca
DMSF, non che l'indice sia completo o funzionante. `unavailable` indica che
Xapian non risulta configurato; `not_attempted` indica l'assenza di progetti
autorizzati. Un risultato non troncato non garantisce una ricerca esaustiva.

**MCP:** l'integrazione riguarda la chat AI Helper. Questa versione non aggiunge
automaticamente gli strumenti DMSF all'endpoint MCP nativo di AI Helper.

## Test, disattivazione e licenza

La suite autonoma usa Ruby e Minitest; è disponibile anche un controllo della
registrazione dentro un ambiente Redmine reale. Comandi e limiti delle
verifiche sono in [docs/testing.md](docs/testing.md).

Per disattivare l'estensione, rimuovi la variabile di attivazione dai processi
Redmine e riavviali, oppure disabilita l'invio degli allegati in AI Helper.
Per disinstallarla, rimuovi la directory del plugin e riavvia Redmine: non ci
sono migrazioni dell'estensione da annullare. La disattivazione non cancella
messaggi o analisi già presenti nella cronologia AI Helper.

La licenza scelta è **GPL-3.0-or-later**, compatibile con DMSF. Gli avvisi MIT
del codice proveniente da AI Helper sono conservati integralmente in
[LICENSES/redmine_ai_helper-MIT.txt](LICENSES/redmine_ai_helper-MIT.txt).
La scelta non modifica le licenze dei progetti originali. Testo completo e
attribuzioni: [LICENSE](LICENSE), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
