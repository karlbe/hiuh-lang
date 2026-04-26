# HIUH - Svensk programmering på mobilvänligt språk

> **Mobilvänlig programmering utan specialtecken!**

## Filosofin bakom HIUH

- **Inga specialtecken** –inga `{}`, `[]`, `;`, `:`, `!`, `"` som är svåra på mobil
- **Svenska nyckelord** – hela meningar istället för symboler
- **Hårt typat** – datatyper ska upptäckas redan vid kompilering, inte vid körning
- **Indenteringsbaserat** – block bestäms av indentering (som Python)

## Designprinciper

### Inga citattecken, inga hakparenteser, inget plus!
**Citattecken (`"`, `'`) är JÄVULENS PÅFUND!** Förbjudna.
**Hakparenteser (`[]`) är JÄVULENS PÅFUND!** Förbjudna.
**Plus (`+`) är JÄVULENS PÅFUND!** Förbjudet för strängar.

Istället för `text + text` → `text sammanfogat med text`
Istället för `lista[i]` → `element i ur lista`
Istället för `text[i]` → `tecken i ur text`

Istället för `Skriv "hej"` → `Skriv hej` (allt efter kommandot är texten!)

För att skriva ut en variabels värde: `Skriv värdet av x`

Detta gör HIUH extremt lätt att skriva på ett mobiltangentbord.

## Nyckelord

### Variabler & Tilldelning

```
Sätt <namn> till <uttryck>
```

Exempel:
```
Sätt x till 5
Sätt namn till Kalle
Sätt pris till 99.50
```

### Utskrift

```
Skriv <text>
```

Exempel:
```
Skriv Hej världen
Skriv Variabeln x är
```

### Villkor

```
Om <villkor> så
    <satser>
Annars
    <satser>
Hejdå
```

Exempel:
```
Om x är större än 10 så
    Skriv Stort
Annars
    Skriv Litet
Hejdå
```

### Loopar

```
För <variabel> från <start> till <slut>
    <satser>
Hejdå
```

Exempel:
```
För i från 1 till 10
    Skriv i
Hejdå
```

```
Medan <villkor>
    <satser>
Hejdå
```

### Funktioner

```
Grej <namn>(<parametrar>)
    <satser>
Grej SLUT
```

### Jämförelseoperatorer

| Operator | Betydelse |
|----------|-----------|
| `är` | lika med (`==`) |
| `är inte` | inte lika med (`!=`) |
| `är större` | större än (`>`) |
| `är mindre` | mindre än (`<`) |
| `är större eller` | större än eller lika med (`>=`) |
| `är mindre eller` | mindre än eller lika med (`<=`) |

### Aritmetik

| Operator | Betydelse |
|----------|-----------|
| `plus` | addition (`+`) |
| `minus` | subtraktion (`-`) |
| `gånger` | multiplikation (`*`) |
| `delat` | division (`/`) |

### Logiska operatorer

| Operator | Betydelse |
|----------|-----------|
| `och` | logiskt OCH (`&&`) |
| `eller` | logiskt ELLER (`\|\|`) |
| `inte` | logiskt INTE (`!`) |

### Listor

```
Sätt <namn> till lista                      # Skapa tom lista
Sätt <namn> till lista av 1, 2, 3           # Skapa lista med värden
Lägg till <värde> till <lista>              # Lägg till element
Antal element i <lista>                      # Antal element
element <index> ur <lista>                   # Hämta element
```

### Strängmanipulation

```
<text> sammanfogat med <text>               # Konkatenera
tecken <index> ur <text>                    # Hämta tecken
```

### File-I/O

```
Öppna <fil> för läsning som <namn>         # Öppna fil
Läs <namn>                                  # Läs fil
SkrivTillFil <fil>, <text>                  # Skriv till fil
```

### Programavslutning

```
Jag måste gå nu                              # exit(0)
Jag måste gå nu <kod>                       # exit(kod)
```

### Datatyper (planerade för hiuhpp)

| Typ | Beskrivning | Exempel |
|-----|-------------|---------|
| `Heltal` | Heltal utan decimaler | `5`, `-42`, `0` |
| `Decimal` | Flyttal | `3.14`, `-0.5` |
| `Text` | Strängar | `"Hej"` |
| `JaNej` | Boolean | `Ja`, `Nej` |

### Inbyggda funktioner

| Funktion | Beskrivning |
|----------|-------------|
| `Slumptal` | Returnerar ett slumpmässigt heltal 0-99 |
| `input(<prompt>)` | Läser in från användaren |
| `Längd(<lista>)` | Returnerar antalet element i en lista |

## Exempelprogram

### Hej världen
```
Skriv Hej världen
```

### Variabler och aritmetik
```
Sätt x till 10
Sätt y till 20
Sätt z till x plus y
Skriv värdet av z
```

### Villkor
```
Sätt betyg till 85
Om betyg är större eller 90 så
    Skriv Utmärkt
Annars om betyg är större eller 70 så
    Skriv Bra
Annars
    Skriv Måste bli bättre
Hejdå
```

### For-loop
```
Sätt summa till 0
För i från 1 till 100
    Sätt summa till summa plus i
Hejdå
Skriv summa
```

## Kompilering

### WebAssembly (alla plattformar)
```bash
python3 hiuh.py program.hiuh output.html
```

Öppna `output.html` i en webbläsare!

### Native Linux
```bash
python3 native/hiuh-native.py program.hiuh output
chmod +x output
./output
```

## Datatypssystem i hiuhpp

Ett centralt mål för `hiuhpp` är **statisk typkontroll**. Följande kontroller ska ske vid kompilering:

### Typfel som ska upptäckas

1. **Typ-matchning i uttryck**
   ```
   Sätt x till 5 plus "text"  # FEL: kan inte addera Heltal + Text
   ```

2. **Typ-matchning i villkor**
   ```
   Om "hej" är större än 5  # FEL: kan inte jämföra Text > Heltal
   ```

3. **Otilldelnade variabler**
   ```
   Skriv x  # FEL: x har inte tilldelats ett värde
   ```

4. **Fel antal parametrar till funktioner**
   ```
   Sätt resultat till Slumptal(5)  # FEL: Slumptal tar inga parametrar
   ```

5. **Använda variabel före deklaration**
   ```
   Sätt y till x plus 1  # FEL: x är inte deklarerad
   Sätt x till 5
   ```

### Typ-regler

| Operation | Tillåtna typer | Resultat |
|-----------|---------------|----------|
| `plus`, `minus`, `gånger`, `delat` | Heltal, Decimal | samma typ |
| `är`, `är inte`, `är större`, `är mindre` | måste matcha | JaNej |
| `Skriv` | alla typer | Text (konverterar automatiskt) |
| `Sätt x till` | alla typer | samma typ som värdet |

## Bidra

Kolla gärna `hiuhpp`-grenen för arbete med hårt typning och felupptäckt!

## Licens

MIT License – gör vad du vill med koden!
