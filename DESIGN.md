# HIUH Språkdesign

Officiellt designdokument. Beslut här är fattade — implementationsdetaljer
diskuteras i TODO.md.

---

## Principer

- Nära maskinen, men inget läcker på användaren
- Kompileringsfel hellre än körtidsfel
- En sak beter sig likadant överallt — inga specialfall
- Roligt att skriva
- All giltig HIUH-kod ska kunna skrivas utan specialtecken utom `,` och `.`
  — inga `{} [] () ! @ # $ % & * + = < > / \ | : ; " ' ~`
  Punkt används för kommentarer, komma för argumentlistor.

---

## Typsystem

**Statisk typning, inferred från tilldelning.**

Kompilatorn härleder typen från det första värdet en variabel tilldelas.
Ingen explicit typdeklaration krävs av användaren.

```
Sätt x till 5          . x är Heltal — kompilatorn vet detta
Sätt namn till Läs     . namn är Text — kompilatorn vet detta
```

Typkonflikt är ett kompileringsfel:

```
Sätt x till namn       . FEL: kan inte tilldela Text till Heltal
```

### Inbyggda typer

| Typ | Beskrivning | Internt |
|---|---|---|
| `Heltal` | 64-bit heltal | register (%r12 etc) |
| `Text` | sträng, max 256 byte | namnlös buffert |
| `Sant` / `Falskt` | boolesk | heltal 1 / 0 |

Inga pekare. Inga buffertar. Inga adresser. Användaren ser bara namn.

### Funktionssignaturer

Returtyp deklareras med `ge`:

```
Funktion längd med t är Text
ge Heltal
    ...
Hejdå
```

Parametrar får sin typ från anropssidan — kompilatorn kontrollerar att
rätt typ skickas in.

---

## Minnesmodell

**Värdesemantik för alla typer.**

Tilldelning kopierar alltid. Två variabler delar aldrig minne.
`Text` beter sig precis som `Heltal` — ingen skillnad i hur användaren
resonerar om dem.

```
Sätt a till "hej"
Sätt b till a           . b får en kopia — oberoende av a
Sätt a till "då"
SkrivNyRad b            . skriver "hej"
```

Under huven: tilldelning mellan två `Text`-variabler kompileras till
`KopieraBuffer`. Användaren ser aldrig detta.

### Textbuffertar

Varje `Text`-variabel har en kompilator-genererad buffert (256 byte).
Användaren namnger aldrig bufferten — det är kompilatorns ansvar.

Buffertnamn genereras som `_text_0`, `_text_1` etc. och är inte
giltiga identifierare i HIUH (inleds med `_`).

### Spill / overflow

Om en `Text`-operation skulle skriva mer än 256 byte:

- Programmet avbryts med ett tydligt felmeddelande
- Tyst trunkering sker aldrig — det korrupterar data utan varning

Felmeddelande (runtime):
```
FEL: Text overflow i variabel 'namn' (max 256 tecken)
```

Framtida möjlighet: `Text storlek 1024` för att deklarera större text.
Inte implementerat ännu — 256 räcker för det mesta.

---

## Funktionsanrop

**Verkliga call/ret — inte inlining.**

Funktioner är riktiga maskinkodsfunktioner med egna stackramar.
Windows x64 ABI används (även på Linux för enkelhetens skull — att
byta till System V ABI är en separat diskussion).

- Argument: upp till 4, skickas i register (rcx, rdx, r8, r9)
- Returvärde: i rax
- Variabler inuti en funktion är lokala — syns inte utanför

Syntax:

```
Anropa func_name med arg1, arg2

Sätt x till Anropa func_name med arg1, arg2
```

---

## Vad som medvetet utelämnats

| Koncept | Varför inte |
|---|---|
| Pekare | Exponerar maskindetaljer, källa till svåra buggar |
| Buffertar (namngivna) | Ersätts av Text-typen |
| Dynamisk typning | Fel hittas för sent |
| Manuell minneshantering | Inte nödvändigt med värdesemantik + fast storlek |
| Flyttal | Inte behövt ännu — läggs till när behovet finns |
