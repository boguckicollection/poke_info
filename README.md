## poke info

Skrypt generuje infografiki na potrzeby mediów społecznościowych na podstawie danych z pliku CSV.

### Schemat pliku CSV
Plik wejściowy powinien zawierać kolumny: `Tytul`, `Kategoria`, `Grafika`, `Tło`, `Logo`, `Opis`, `Źródło`.
- Wartość w kolumnie `Tło` wskazuje adres URL grafiki tła używanej na planszy.
- Kolumna `Grafika` zawiera adresy URL grafik kart; zapisuje się je w niej w postaci listy oddzielonej średnikiem (`;`).
- Pozostałe kolumny (`Tytul`, `Kategoria`, `Logo`, `Opis`, `Źródło`) są wykorzystywane do wypełnienia treści karty.

### Ładowanie grafik
Każdy adres umieszczony w kolumnie `Grafika` jest wykorzystywany wyłącznie jako grafika karty zarówno dla stron z treściami, jak i rankingów w kategorii **Trendy cen**.
Grafika tła planszy jest ładowana z adresu z kolumny `Tło`.
