import pandas as pd
import rasterio
import re

# ==========================================
# KONFIGURACJA PLIKÓW I PARAMETRÓW
# ==========================================
PLIK_CSV_Z_GTB = 'gtb_summary.csv'
PLIK_TIF = 'indata_WVL2021_5m_byte_ok_closing_3_byte.tif'
PLIK_WYNIKOWY = 'gtb_summary_wspolrzedne_rozbite_metry.csv'

ROZMIAR_PIKSELA_M = None 

# ==========================================
# 0. POBIERANIE METADANYCH Z RASTRA
# ==========================================
print(f"Otwieranie rastra: {PLIK_TIF} w celu pobrania metadanych...")
try:
    with rasterio.open(PLIK_TIF) as src:
        if ROZMIAR_PIKSELA_M is None:
            ROZMIAR_PIKSELA_M = round(src.res[0], 2)
            print(f"--> Automatycznie wykryto rozmiar piksela: {ROZMIAR_PIKSELA_M} m")
        else:
            print(f"--> Używam ręcznie zdefiniowanego rozmiaru piksela: {ROZMIAR_PIKSELA_M} m")
            
        raster_transform = src.transform
except FileNotFoundError:
    print(f"BŁĄD: Nie znaleziono rastra {PLIK_TIF}. Upewnij się, że plik istnieje.")
    exit()

# ==========================================
# 1. WCZYTYWANIE DANYCH Z GTB
# ==========================================
print(f"Wczytywanie tabeli {PLIK_CSV_Z_GTB}...")
df = pd.read_csv(PLIK_CSV_Z_GTB, sep=None, engine='python', skiprows=1)
df.columns = df.columns.str.strip()

kolumna_id = next((c for c in df.columns if 'ID' in c.upper()), None)
kolumna_dystansu_oryg = 'clength' if 'clength' in df.columns else 'proximity'
kolumna_nbr = next((c for c in df.columns if 'nbr' in c.lower()), None)

if not kolumna_id or not kolumna_dystansu_oryg:
    print("BŁĄD: Nie znaleziono wymaganych kolumn (ID / clength) w pliku wejściowym.")
    exit()

# ==========================================
# 2. PRZELICZANIE DYSTANSU NA METRY
# ==========================================
dystans_piksele = pd.to_numeric(df[kolumna_dystansu_oryg].astype(str).str.replace(',', '.'), errors='coerce')
df['clength_m'] = dystans_piksele * ROZMIAR_PIKSELA_M
df = df.dropna(subset=['clength_m'])

# ==========================================
# 3. IDENTYFIKACJA I USUWANIE DUPLIKATÓW (SZYBKA ŚCIEŻKA)
# ==========================================
print("Tworzenie sygnatur par i usuwanie duplikatów...")

def szybka_sygnatura(tekst):
    """Lekka funkcja wyciągająca TYLKO numery ID w celu znalezienia dubletów"""
    znalaziska = re.findall(r'(\d+)\s*-', str(tekst))
    if len(znalaziska) >= 2:
        return tuple(sorted([int(z) for z in znalaziska]))
    return None

df['Sygnatura_ID'] = df[kolumna_id].apply(szybka_sygnatura)
df = df.dropna(subset=['Sygnatura_ID'])

ile_przed = len(df)
# Sortujemy by na górze znalazły się najkrótsze korytarze, a potem odrzucamy resztę dubletów
df = df.sort_values(by='clength_m', ascending=True)
df = df.drop_duplicates(subset=['Sygnatura_ID'], keep='first')
ile_po = len(df)

print(f"--> Usunięto {ile_przed - ile_po} powtarzających się lokalizacji korytarzy.")
print(f"--> Pozostało {ile_po} unikalnych połączeń do pełnej analizy.")

# ==========================================
# 4. ROZBIJANIE I PRZELICZANIE POWIERZCHNI NA M2 (TYLKO DLA UNIKATÓW)
# ==========================================
print("Rozbijanie połączonej kolumny i przeliczanie powierzchni na m2 (dla odfiltrowanych danych)...")

def parsowanie_obiektow(tekst):
    """Ciężka funkcja uruchamiana tylko na zredukowanym zbiorze"""
    znalaziska = re.findall(r'(\d+)\s*-\s*(\d+\.?\d*)', str(tekst))
    dane = {}
    
    for i, (obj_id, area) in enumerate(znalaziska, start=1):
        dane[f'ID_{i}'] = int(obj_id)
        powierzchnia_m2 = float(area) * (ROZMIAR_PIKSELA_M ** 2)
        dane[f'Area_m2_{i}'] = round(powierzchnia_m2, 2)
        
    return pd.Series(dane)

nowe_kolumny = df[kolumna_id].apply(parsowanie_obiektow)
df = pd.concat([df, nowe_kolumny], axis=1)

# ==========================================
# 4.5 OPCJONALNE FILTROWANIE KOŃCOWE
# ==========================================
print("Zastosowanie opcjonalnych filtrów (jeśli aktywne)...")
df = df[df['clength_m'] <= 50.0]

area_cols = [col for col in df.columns if col.startswith('Area_m2_')]
df = df[df[area_cols].min(axis=1) >= 5000.0]

id_cols = [col for col in df.columns if col.startswith('ID_')]
df = df[~df[id_cols].isin([101]).any(axis=1)]

# ==========================================
# 5. PRZELICZANIE WSPÓŁRZĘDNYCH PRZESTRZENNYCH
# ==========================================
print("Przeliczanie komórek na współrzędne geograficzne...")
wspolrzedne = [rasterio.transform.xy(raster_transform, row, col) 
               for row, col in zip(df['WS-Y'], df['WS-X'])]

df['Geo_X'] = [int(round(krotka[0])) for krotka in wspolrzedne]
df['Geo_Y'] = [int(round(krotka[1])) for krotka in wspolrzedne]

df = df.drop(columns=['Sygnatura_ID'])

# ==========================================
# 6. ZAPIS DO PLIKU
# ==========================================
kolumny_poczatkowe = ['Geo_X', 'Geo_Y', 'clength_m']
if kolumna_nbr:
    kolumny_poczatkowe.append(kolumna_nbr)
    
kolumny_koncowe = kolumny_poczatkowe + \
                  [col for col in df.columns if col.startswith('ID_') or col.startswith('Area_m2_')] + \
                  [col for col in df.columns if col not in kolumny_poczatkowe and not (col.startswith('ID_') or col.startswith('Area_m2_'))]

df = df.reindex(columns=kolumny_koncowe)

df.to_csv(PLIK_WYNIKOWY, index=False, sep=';', decimal=',')
print(f"Gotowe! Wygenerowano wyczyszczony plik przestrzenny: {PLIK_WYNIKOWY}")