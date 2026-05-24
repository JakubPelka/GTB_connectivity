GTB LANDSCAPE CONNECTIVITY & DENDRITE ANALYZER

Kompletny obieg pracy (workflow) oraz zestaw skryptów w Pythonie do zaawansowanej analizy łączności krajobrazowej (korytarzy ekologicznych).
Proces ten pozwala na przetworzenie surowych danych rastrowych, analizę bliskości (Proximity) w GuidosToolbox, georeferencję i czyszczenie danych, aż po wyliczenie najbardziej opłacalnych wielokrokowych łańcuchów (dendrytów) na podstawie wskaźnika ROI (Zysk / Koszt).

WYMAGANIA:
QGIS / SAGA GIS (do preprocessingu rastra)
GuidosToolbox (GTB)
Python 3.6+ z bibliotekami: pandas, networkx, rasterio (instalacja komendą: pip install pandas networkx rasterio)

PEŁNY WORKFLOW (KROK PO KROKU):
Proces opiera się na następującym łańcuchu operacji:
TIF -> Morphological Filter -> Byte -> Proximity (GTB) -> Coordinates & Filtering (Python 1) -> Chain of Gain (Python 2)

KROK 1: PREPROCESSING RASTRA (QGIS / SAGA)
Zanim dane trafią do GTB, musimy usunąć szum i mikro-przerwy, które wygenerowałyby tysiące fałszywych korytarzy.

Morphological Filter: W QGIS (używając algorytmów SAGA) zastosuj filtr morfologiczny w trybie Closing (Zamknięcie). Operacja ta scala bliskie obiekty (dylatacja + erozja) i eliminuje luki o szerokości 1-2 pikseli.

Konwersja na Byte: Zapisz przefiltrowany wynik jako GeoTIFF w formacie 8-bitowym (Byte), który jest wymaganym formatem wejściowym dla oprogramowania GuidosToolbox.

KROK 2: ANALIZA PROXIMITY (GUIDOSTOOLBOX)

Zaimportuj przygotowany plik TIF do GTB.

Uruchom analizę Proximity.

Po zakończeniu analizy, wyeksportuj tabelę wyników (Spreadsheet summary) i zapisz ją jako gtb_summary.csv w folderze ze skryptami Pythona.

KROK 3: GEOREFERENCJA, PARSOWANIE I FILTROWANIE (SKRYPT 1)
Plik z GTB zawiera powielone korytarze, połączone kolumny i brak mu współrzędnych przestrzennych.
Uruchom skrypt: python georef_gtb.py

Co robi ten skrypt?

Coordinates: Przelicza lokalne piksele (WS-X, WS-Y) na prawdziwe, zaokrąglone współrzędne geograficzne w metrach, korzystając z oryginalnego pliku TIF.

Rozbijanie Kolumn: Parsuje połączoną kolumnę IDs(area) wypluwając czyste kolumny: ID_1, Area_1, ID_2, Area_2 (co ułatwi późniejsze filtrowanie drobnicy w QGIS/Excelu).

Filtering (Usuwanie Duplikatów): Jeśli dwa obiekty mają długą granicę i GTB znalazło między nimi 5 korytarzy, skrypt odrzuca 4 najgorsze i zostawia tylko jedno, najkrótsze i optymalne połączenie dla każdej pary obiektów.

Wynik: Plik gtb_summary_wspolrzedne_rozbite.csv gotowy do importu do QGIS (jako punkty).

KROK 4: ANALIZA ŁAŃCUCHOWA "CHAIN OF GAIN" (SKRYPT 2)
Mając wyczyszczone i unikalne korytarze, możemy poszukać optymalnych ciągów zmian i "dendrytów" o określonej głębokości (np. 3-4 skoki).
W pliku gtb_analiza.py upewnij się, że PLIK_WEJSCIOWY jest ustawiony na plik z poprzedniego kroku: gtb_summary_wspolrzedne_rozbite.csv.
Uruchom skrypt: python gtb_analiza.py

Co robi ten skrypt?

Buduje topologiczny graf sieci (obiekty to węzły, korytarze to krawędzie).

Odrzuca korytarze o długości powyżej zdefiniowanego progu (MAX_DYSTANS, np. > 10 pix).

Przeszukuje rekurencyjnie łańcuchy do ustalonej głębokości (MAX_KROKOW).

Oblicza Zysk Dodany (nową przyłączoną powierzchnię siedlisk bez uwzględniania obiektu startowego) i dzieli go przez całkowity koszt dystansu.

Generuje wskaźnik ROI (Return on Investment).

Wynik: Plik Najlepsze_Dendryty_Wynik.csv zawierający posortowaną listę najbardziej opłacalnych inwestycji korytarzowych.

GŁÓWNE PARAMETRY SKRYPTÓW (DO EDYCJI W KODZIE)

W pliku georef_gtb.py:
PLIK_CSV_Z_GTB = 'gtb_summary.csv' (Surowy plik z GTB)
PLIK_TIF = 'indata_WVL2021_5m_byte.tif' (Twój oryginalny GeoTIFF do georeferencji)

W pliku gtb_analiza.py:
PLIK_WEJSCIOWY = 'gtb_summary_wspolrzedne_rozbite.csv' (Plik po przefiltrowaniu z Kroku 3)
MAX_DYSTANS = 10.0 (Twardy limit odrzucający korytarze o długości > 10 pikseli)
MAX_KROKOW = 4 (Maksymalna głębokość łańcucha do przeszukania)
