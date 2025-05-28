# XMODEM
CLI app for sending and receiving data with XMODEM protocol.

## 1. Teoria protokołu XMODEM

### 1.1 Wprowadzenie

XMODEM to protokół transmisji szeregowej opracowany w 1977 roku przez Warda Christensena. Jest to jeden z najstarszych i najszerzej używanych protokołów transferu plików, który mimo swojego wieku, nadal znajduje zastosowanie w systemach wbudowanych, telekomunikacji i innych środowiskach wymagających niezawodnej transmisji danych.

### 1.2 Cechy protokołu XMODEM

- **Niezawodność**: Wykorzystuje mechanizmy sum kontrolnych (checksum) lub CRC (Cyclic Redundancy Check) do wykrywania błędów transmisji.
- **Odporność na błędy**: Obsługuje retransmisje uszkodzonych bloków danych.
- **Prostota**: Łatwy w implementacji, co przyczyniło się do jego popularności.
- **Blokowy transfer**: Dane przesyłane są w blokach o stałym rozmiarze (zwykle 128 bajtów).

### 1.3 Warianty protokołu

1. **XMODEM (oryginalny)** - używa prostej 8-bitowej sumy kontrolnej
2. **XMODEM-CRC** - używa 16-bitowego CRC (Cyclic Redundancy Check) dla lepszej detekcji błędów
3. **XMODEM-1K** - używa większych bloków danych (1024 bajty) dla zwiększenia wydajności
4. **XMODEM-1K/G** - wersja bez potwierdzeń dla szybszej transmisji w niezawodnych łączach

W tej implementacji zrealizowane są warianty XMODEM (oryginalny) oraz XMODEM-CRC.

### 1.4 Znaki kontrolne

XMODEM wykorzystuje kilka specjalnych znaków kontrolnych:

- **SOH (Start of Header, 0x01)** - oznacza początek bloku danych
- **EOT (End of Transmission, 0x04)** - oznacza koniec transmisji
- **ACK (Acknowledge, 0x06)** - potwierdzenie prawidłowego odbioru danych
- **NAK (Negative Acknowledge, 0x15)** - sygnał nieprawidłowego odbioru danych lub żądanie rozpoczęcia transmisji w trybie checksum
- **CAN (Cancel, 0x18)** - anulowanie transmisji
- **C (0x43)** - żądanie rozpoczęcia transmisji w trybie CRC

### 1.5 Format pakietu

Pakiet XMODEM ma następującą strukturę:

```
+-----+------------+-----------+--------+--------------+
| SOH | Blok numer | Dopełnienie | Dane | Suma kontrolna |
| (1) |    (1)    |    (1)    | (128) |   (1 lub 2)   |
+-----+------------+-----------+--------+--------------+
```

Gdzie:
- **SOH** - 1 bajt oznaczający początek bloku
- **Blok numer** - numer sekwencyjny bloku (1-255, wraca do 1 po 255)
- **Dopełnienie** - dopełnienie numeru bloku do 255 (255 - numer bloku)
- **Dane** - 128 bajtów danych
- **Suma kontrolna** - 1 bajt sumy kontrolnej (dla XMODEM) lub 2 bajty CRC (dla XMODEM-CRC)

### 1.6 Algorytm działania

#### Rozpoczęcie transmisji:
1. Odbiornik inicjuje transmisję wysyłając NAK (dla standardowego XMODEM) lub znak 'C' (dla XMODEM-CRC).
2. Nadajnik czeka na inicjację od odbiornika.

#### Transmisja danych:
1. Nadajnik dzieli plik na bloki po 128 bajtów.
2. Dla każdego bloku nadajnik:
   - Wysyła SOH
   - Wysyła numer bloku
   - Wysyła dopełnienie numeru bloku (255 - numer bloku)
   - Wysyła 128 bajtów danych
   - Wysyła sumę kontrolną lub CRC

3. Odbiornik:
   - Odbiera blok danych
   - Weryfikuje numer bloku i jego dopełnienie
   - Oblicza i weryfikuje sumę kontrolną lub CRC
   - Wysyła ACK (jeśli dane są poprawne) lub NAK (jeśli występują błędy)

4. Jeśli nadajnik otrzyma NAK, ponawia transmisję bloku.

#### Zakończenie transmisji:
1. Po wysłaniu wszystkich bloków danych, nadajnik wysyła EOT.
2. Odbiornik potwierdza odbiór EOT wysyłając ACK.

### 1.7 Algorytmy sum kontrolnych

#### 1.7.1 Prosta suma kontrolna (Checksum)
Jest to suma wszystkich bajtów w bloku danych, modulo 256 (8 bitów). Jest prosta w implementacji, ale oferuje ograniczoną detekcję błędów.

#### 1.7.2 CRC-16 (CCITT)
CRC-16 oferuje znacznie lepszą detekcję błędów niż prosta suma kontrolna. Wykorzystuje wielomian 0x1021 (x^16 + x^12 + x^5 + 1). Jest standardem w XMODEM-CRC.

#### Wyjaśnienie operacji bitowych w CRC

- Oblicza otrzymany CRC: `received_crc = (crc_bytes[0] << 8) | crc_bytes[1]`
  
  Ten zapis służy do połączenia dwóch bajtów CRC w jedną 16-bitową wartość. Rozbijmy to na poszczególne operacje:
  
  1. `crc_bytes[0] << 8` - przesuwa pierwszy bajt (starszy bajt) o 8 bitów w lewo, 
     co umieszcza go na pozycji bardziej znaczących bitów w 16-bitowej liczbie.
     Na przykład, jeśli `crc_bytes[0]` ma wartość `0x12`, po przesunięciu otrzymamy `0x1200`.
  
  2. `crc_bytes[1]` - to drugi bajt (młodszy bajt) CRC.
     Na przykład, jeśli `crc_bytes[1]` ma wartość `0x34`.
  
  3. Operator `|` (bitowe OR) łączy te dwie wartości, umieszczając pierwszy bajt 
     na bardziej znaczących pozycjach, a drugi na mniej znaczących.
     Kontynuując przykład: `0x1200 | 0x34 = 0x1234`.
  
  Operacja ta rekonstruuje oryginalną 16-bitową liczbę CRC z dwóch 8-bitowych bajtów,
  które zostały przesłane w protokole XMODEM-CRC.
