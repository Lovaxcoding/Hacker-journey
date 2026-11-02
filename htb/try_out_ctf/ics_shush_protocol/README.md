# Writeup – HTB Hardware / ICS « Shush Protocol »

## Contexte

On dispose d'une archive `ics_shush_protocol.zip` contenant une unique capture réseau :

```
traffic.pcapng
```

Le nom du challenge (« Shush Protocol ») et le contexte **ICS** (Industrial Control Systems) suggèrent une analyse de trafic industriel — typiquement du **Modbus TCP** (port 502), protocole très répandu dans les environnements OT/ICS.

## Analyse

### Reconnaissance initiale

On ouvre la capture dans Wireshark (ou `tshark`) :

```bash
tshark -r traffic.pcapng
```

Ou directement sur les flux TCP :

```bash
tshark -r traffic.pcapng -q -z conv,tcp
```

On repère rapidement une connexion vers le **port 502** → c'est du **Modbus TCP**.

### Filtrage du trafic Modbus

```bash
tshark -r traffic.pcapng -Y "modbus" -V
```

Ou dans Wireshark :

```
modbus
```

On identifie une trame contenant des **données inhabituelles** : au lieu de valeurs de registres classiques, le payload contient une chaîne ASCII lisible.

### Analyse manuelle de la trame

L'utilisateur a extrait le hexdump de la trame intéressante. Décortiquons-la couche par couche.

#### En-tête Ethernet (14 octets)

```
00 11 22 33 44 55   → MAC destination
08 00 27 c6 eb 78   → MAC source
08 00               → EtherType IPv4
```

#### En-tête IP (20 octets)

```
45 00         → IPv4, IHL=5 (20 octets)
00 6d         → Longueur totale = 109 octets
6b 40         → Identification
40 00         → Flags (DF) + fragment offset 0
40            → TTL = 64
06            → Protocole = TCP
e9 78         → Checksum
c0 a8 b2 69   → IP source   = 192.168.178.105
c0 a8 b2 17   → IP dest     = 192.168.178.23
```

#### En-tête TCP (32 octets avec options)

```
9b d0         → Port source = 39888
01 f6         → Port destination = 502  ← Modbus TCP
e7 ac c8 1a   → Numéro de séquence
3c 59 42 64   → Numéro d'acquittement
80 18         → Data offset = 8 (32 octets), flags PSH+ACK
00 fb         → Fenêtre
e6 31         → Checksum
00 00         → Pointeur urgent
01 01 08 0a ... → Options (NOP, NOP, Timestamp)
```

Le port destination **502** confirme : c'est bien du **Modbus TCP**.

#### En-tête MBAP (Modbus Application Protocol, 7 octets)

Le payload TCP commence ici :

```
00 0c   → Transaction ID
00 00   → Protocol ID (0 = Modbus)
00 33   → Length = 51 octets
00      → Unit ID
```

#### PDU Modbus

```
66              → Function code = 0x66 (102) — fonction custom !
00 10           → Champ spécifique (probablement une longueur)
2e              → 46 (longueur de la charge utile ?)
48 54 42 7b ... → Données ASCII
```

Le **function code `0x66` (102)** est **non standard** : Modbus définit les codes 1 à 127, mais 102 n'est pas documenté dans la spécification officielle. C'est le signe d'une **extension custom** du protocole — exactement ce que suggère le nom du challenge et le flag.

### Extraction de la charge utile

Le reste du payload est de l'ASCII pur :

```
2e 48 54 42 7b 35 30 6d 33 37 31 6d 33 35 5f 63 75 35 37 30
6d 5f 70 32 30 37 30 63 30 31 5f 34 32 33 5f 6e 30 37 5f 33
6e 30 75 39 68 37 7d
```

En convertissant l'hexadécimal en ASCII :

```
.HTB{50m371m35_cu570m_p2070c01_423_n07_3n0u9h7}
```

Le `.` initial est le champ `2e` (longueur = 46) qui précède la chaîne. Le flag est donc :

```
HTB{50m371m35_cu570m_p2070c01_423_n07_3n0u9h7}
```

## Exploitation alternative (Wireshark GUI)

Pour aller plus vite :

1. Ouvrir `traffic.pcapng` dans Wireshark
2. Filtrer sur `tcp.port == 502` (ou `modbus`)
3. Clic-droit sur la trame → **Follow → TCP Stream**
4. Le flag apparaît directement en clair dans le flux ASCII, entouré de `HTB{...}`

## Décodage du leet speak

| Leet | Sens |
|---|---|
| `50m371m35` | sometimes |
| `REDACTED` | custom |
| `REDACTED` | protocol |
| `423` | are |
| `n07` | not |
| `3n0u9h7` | enough |

→ **"sometimes custom protocol are not enough"**

Un flag qui résume bien le challenge : le protocole Modbus a été **étendu avec une fonction custom (`0x66`)**, et c'est précisément cette extension non standard qui transporte le flag. Le message sous-entend qu'un protocole custom n'est pas forcément plus sûr — un classique des environnements ICS/OT où la sécurité par l'obscurité est encore répandue.

## Flag

```
HTB{50m371m35_REDACTED_423_n07_3n0u9h7}
```

## Leçons retenues

- **Modbus TCP = port 502** : réflexe immédiat en analyse ICS. Un simple `tcp.port == 502` filtre tout le bruit.
- Les **function codes Modbus non standard** (> 100, ou non documentés) doivent attirer l'attention : ils peuvent transporter des données arbitraires, y compris des flags.
- **Follow TCP Stream** dans Wireshark permet de lire rapidement tout payload ASCII — plus rapide que le hexdump manuel.
- Le **hexdump manuel** reste utile pour comprendre la structure exacte d'une trame (MBAP + PDU) et identifier les champs custom.
- En environnement **ICS/OT**, la sécurité par l'obscurité (protocole custom) est **une mauvaise pratique** : les données restent visibles en clair.

## Outils recommandés

- **Wireshark** — analyse graphique, `Follow TCP Stream`, filtres `modbus` / `tcp.port == 502`
- **tshark** — analyse en ligne de commande, scriptable
- **`xxd`** / `hexdump` — inspection brute d'un payload
- **`echo "..." | xxd -r -p`** — conversion hex → ASCII rapide :

  ```bash
  echo "48 54 42 7b 35 30 6d 33 37 31 6d 33 35 5f 63 75 35 37 30 6d 5f 70 32 30 37 30 63 30 31 5f 34 32 33 5f 6e 30 37 5f 33 6e 30 75 39 68 37 7d" | xxd -r -p
  # HTB{50m371m35_cu570m_p2070c01_423_n07_3n0u9h7}
  ```
