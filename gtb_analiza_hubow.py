import pandas as pd
import networkx as nx
import itertools
import os

# ==========================================
# 0. KONFIGURACJA PARAMETRÓW
# ==========================================
PLIK_WEJSCIOWY = 'gtb_summary_wspolrzedne_rozbite_metry.csv'
PLIK_WYJSCIOWY = 'Analiza_Hubow_Zasieg_Wynik.csv'

# Krok 1: Jak szeroki może być pojedynczy korytarz/przeskok?
MAX_DYSTANS_M = 50.0  

# Krok 2: Jak daleko zsumowanego lotu/marszu może podjąć się gatunek?
# Wpisz np. 500.0 dla konkretnego zasięgu, 
# ALBO wpisz float('inf') dla MAKSYMALNEGO TEORETYCZNEGO ZASIĘGU (bez limitu paliwa)
ZASIEG_LOTU_M = float('inf') 

# ==========================================
# 1. WCZYTANIE DANYCH I BUDOWA GRAFU
# ==========================================
print(f"Wczytywanie danych z: {PLIK_WEJSCIOWY}...")
if not os.path.exists(PLIK_WEJSCIOWY):
    print(f"BŁĄD: Nie znaleziono pliku {PLIK_WEJSCIOWY}.")
    exit()

df = pd.read_csv(PLIK_WEJSCIOWY, sep=';', decimal=',')
G = nx.Graph()

kolumny_id = [col for col in df.columns if col.startswith('ID_')]
kolumny_area = [col for col in df.columns if col.startswith('Area_m2_')]

for index, row in df.iterrows():
    dystans = float(row['clength_m'])
    
    if dystans > MAX_DYSTANS_M:
        continue
    
    obiekty_w_korytarzu = []
    for kol_id, kol_area in zip(kolumny_id, kolumny_area):
        if pd.notna(row[kol_id]) and pd.notna(row[kol_area]):
            obj_id = int(row[kol_id])
            obj_area = float(row[kol_area])
            obiekty_w_korytarzu.append(obj_id)
            G.add_node(obj_id, area=obj_area)
            
    for pair in itertools.combinations(obiekty_w_korytarzu, 2):
        u, v = pair[0], pair[1]
        if not G.has_edge(u, v) or dystans < G[u][v]['distance']:
            G.add_edge(u, v, distance=dystans)

ilosc_wezlow = G.number_of_nodes()
print(f"Zbudowano graf. Liczba unikalnych siedlisk (węzłów): {ilosc_wezlow}")
print(f"Rozpoczynam masową analizę potencjału (Hub Analysis) dla limitu lotu: {ZASIEG_LOTU_M} m...")

# ==========================================
# 2. MASOWA ANALIZA ZASIĘGU (DIJKSTRA DLA KAŻDEGO WĘZŁA)
# ==========================================
wyniki = []
licznik = 0

# Iterujemy przez KAŻDY obiekt (las/siedlisko) w naszej sieci
for start_node in G.nodes():
    licznik += 1
    
    # Wyświetlamy postęp co 500 obiektów, żeby wiedzieć, że skrypt działa
    if licznik % 500 == 0:
        print(f"  Przeanalizowano {licznik} / {ilosc_wezlow} obiektów...")

    # Magia NetworkX: Znajdź wszystkie obiekty w zasięgu (Dijkstra)
    # Zwraca słownik {ID_osiągniętego_obiektu: dystans_jakim_do_niego_dotarliśmy}
    osiagalne_obiekty = nx.single_source_dijkstra_path_length(
        G, 
        source=start_node, 
        cutoff=ZASIEG_LOTU_M, 
        weight='distance'
    )
    
    powierzchnia_wlasna = G.nodes[start_node]['area']
    zysk_powierzchni = 0
    najdalszy_lot = 0
    
    for obj_id, dystans_lotu in osiagalne_obiekty.items():
        if obj_id == start_node:
            continue
            
        zysk_powierzchni += G.nodes[obj_id]['area']
        if dystans_lotu > najdalszy_lot:
            najdalszy_lot = dystans_lotu

    # Zapisujemy statystyki dla tego konkretnego obiektu
    wyniki.append({
        'ID_Huba': start_node,
        'Wlasna_Powierzchnia_m2': round(powierzchnia_wlasna, 1),
        'Liczba_Sasiadow_w_Zasiegu': len(osiagalne_obiekty) - 1,
        'Max_Dystans_Podrozy_m': round(najdalszy_lot, 1),
        'Dostepna_Nowa_Powierzchnia_m2': round(zysk_powierzchni, 1),
        'Calkowity_Potencjal_Systemu_m2': round(powierzchnia_wlasna + zysk_powierzchni, 1)
    })

# ==========================================
# 3. ZAPIS WYNIKÓW (MAPA HUBÓW)
# ==========================================
print("Zapisywanie wyników...")
df_wyniki = pd.DataFrame(wyniki)

# Sortujemy tak, aby na samej górze były najważniejsze Huby (największy zysk z połączonych obszarów)
df_wyniki = df_wyniki.sort_values(by='Dostepna_Nowa_Powierzchnia_m2', ascending=False)

df_wyniki.to_csv(PLIK_WYJSCIOWY, index=False, sep=';', decimal=',')

print("\n--- TOP 5 NAJWAŻNIEJSZYCH HUBÓW (Niezbędne Węzły Sieci) ---")
print(df_wyniki[['ID_Huba', 'Wlasna_Powierzchnia_m2', 'Liczba_Sasiadow_w_Zasiegu', 'Dostepna_Nowa_Powierzchnia_m2']].head(5).to_string(index=False))
print(f"\nGotowe! Zapisano dane dla wszystkich {ilosc_wezlow} siedlisk do pliku: {PLIK_WYJSCIOWY}")