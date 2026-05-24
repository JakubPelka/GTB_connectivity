import pandas as pd
import networkx as nx
import itertools
import os

# ==========================================
# 0. KONFIGURACJA PARAMETRÓW
# ==========================================
PLIK_WEJSCIOWY = 'gtb_summary_wspolrzedne_rozbite_metry.csv'
PLIK_WYJSCIOWY = 'Najlepsze_Dendryty_Wynik.csv'

# UWAGA: Wartość teraz oznacza METRY, a nie piksele!
MAX_DYSTANS_M = 50.0  # Maksymalna długość pojedynczego korytarza w metrach
MAX_KROKOW = 4        # Maksymalna głębokość przeszukiwania łańcucha

# ==========================================
# 1. WCZYTANIE DANYCH
# ==========================================
print(f"Wczytywanie wyczyszczonych danych z: {PLIK_WEJSCIOWY}")

if not os.path.exists(PLIK_WEJSCIOWY):
    print(f"BŁĄD: Nie znaleziono pliku {PLIK_WEJSCIOWY}.")
    exit()

# Wczytujemy plik wygenerowany przez nasz poprzedni skrypt (separator średnik, przecinek jako dziesiętny)
df = pd.read_csv(PLIK_WEJSCIOWY, sep=';', decimal=',')

# ==========================================
# 2. BUDOWA GRAFU
# ==========================================
G = nx.Graph()
odrzucone_korytarze = 0
dodane_krawedzie = 0

# Automatycznie wykrywamy, ile kolumn ID i Area wygenerował poprzedni skrypt
kolumny_id = [col for col in df.columns if col.startswith('ID_')]
kolumny_area = [col for col in df.columns if col.startswith('Area_m2_')]

print("Budowa topologicznego grafu sieci...")

for index, row in df.iterrows():
    dystans = float(row['clength_m'])
    
    # FILTR: Odrzucamy korytarze dłuższe niż nasz limit
    if dystans > MAX_DYSTANS_M:
        odrzucone_korytarze += 1
        continue
    
    # Wyciągamy wszystkie obiekty, które bierą udział w tym połączeniu
    obiekty_w_korytarzu = []
    
    for kol_id, kol_area in zip(kolumny_id, kolumny_area):
        # Sprawdzamy, czy w danej kolumnie jest faktycznie wartość (nie puste 'NaN')
        if pd.notna(row[kol_id]) and pd.notna(row[kol_area]):
            obj_id = int(row[kol_id])
            obj_area = float(row[kol_area])
            obiekty_w_korytarzu.append(obj_id)
            
            # Dodajemy/aktualizujemy Węzeł w grafie (waga = powierzchnia w m2)
            G.add_node(obj_id, area=obj_area)
            
    # Tworzymy Krawędzie między wszystkimi obiektami na danym skrzyżowaniu
    for pair in itertools.combinations(obiekty_w_korytarzu, 2):
        u, v = pair[0], pair[1]
        
        # Nawet jeśli poprzedni skrypt wyczyścił dublety, zabezpieczamy się na wypadek węzłów wielokrotnych
        if G.has_edge(u, v):
            if dystans < G[u][v]['distance']:
                G[u][v]['distance'] = dystans
        else:
            G.add_edge(u, v, distance=dystans)
            dodane_krawedzie += 1

print(f"Zbudowano graf: {G.number_of_nodes()} obiektów (węzłów) i {G.number_of_edges()} połączeń.")
print(f"Odfiltrowano {odrzucone_korytarze} zbyt długich korytarzy (> {MAX_DYSTANS_M} m).")

# ==========================================
# 3. SILNIK PRZESZUKIWANIA DENDRYTÓW (DFS)
# ==========================================
def pobierz_dendryty(graf, start_node, max_steps):
    """Generuje wszystkie ścieżki z węzła startowego bez zapętleń."""
    stack = [(start_node, [start_node])]
    while stack:
        current, path = stack.pop()
        
        if len(path) > 1:
            yield path
            
        if len(path) - 1 < max_steps:
            for neighbor in graf.neighbors(current):
                if neighbor not in path:
                    stack.append((neighbor, path + [neighbor]))

# ==========================================
# 4. ANALIZA ŚCIEŻEK I WYLICZANIE ROI (ZYSK DODANY)
# ==========================================
print(f"Rozpoczynam iterację po łańcuchach (max {MAX_KROKOW} kroki)...")
wyniki = []
przeanalizowane_sciezki = set()

for start in G.nodes():
    for sciezka in pobierz_dendryty(G, start, max_steps=MAX_KROKOW):
        
        identyfikator_sciezki = tuple(sciezka)
        identyfikator_odwrotny = tuple(reversed(sciezka))
        
        # Eliminacja lustrzanych duplikatów
        if identyfikator_sciezki in przeanalizowane_sciezki or identyfikator_odwrotny in przeanalizowane_sciezki:
            continue
            
        przeanalizowane_sciezki.add(identyfikator_sciezki)
        
        # --- ZYSKI (w metrach kwadratowych) ---
        zysk_calkowity = sum(G.nodes[n]['area'] for n in sciezka)
        powierzchnia_startowa = G.nodes[sciezka[0]]['area']
        zysk_dodany = zysk_calkowity - powierzchnia_startowa
        
        # --- KOSZT (w metrach bieżących) ---
        koszt_dystansu = sum(G[sciezka[i]][sciezka[i+1]]['distance'] for i in range(len(sciezka)-1))
        
        # --- WSKAŹNIK OPŁACALNOŚCI ---
        # ROI mówi nam: ile nowych metrów kwadratowych siedliska "kupujemy" za każdy metr korytarza
        roi = zysk_dodany / (koszt_dystansu if koszt_dystansu > 0 else 0.1)
        
        wyniki.append({
            'Sciezka': " -> ".join(map(str, sciezka)),
            'Skoki': len(sciezka) - 1,
            'Zysk_Calkowity_m2': round(zysk_calkowity, 1),
            'Zysk_Dodany_m2': round(zysk_dodany, 1),
            'Koszt_Dystansu_m': round(koszt_dystansu, 1),
            'ROI': round(roi, 2)
        })

# ==========================================
# 5. SORTOWANIE I ZAPIS WYNIKÓW
# ==========================================
if wyniki:
    wyniki_df = pd.DataFrame(wyniki)
    # Sortowanie od najbardziej opłacalnych
    wyniki_posortowane = wyniki_df.sort_values(by='ROI', ascending=False)
    
    # Zapis do CSV (gotowe do otwarcia w polskim Excelu)
    wyniki_posortowane.to_csv(PLIK_WYJSCIOWY, index=False, sep=';', decimal=',')
    
    print("\n--- TOP 5 NAJLEPSZYCH ŁAŃCUCHÓW INWESTYCYJNYCH ---")
    print(wyniki_posortowane.head(5).to_string(index=False))
    print(f"\nAnaliza zakończona sukcesem. Zapisano wszystkie {len(wyniki)} ścieżek do: {PLIK_WYJSCIOWY}")
else:
    print("\nNie znaleziono żadnych ścieżek spełniających kryteria (sprawdź czy MAX_DYSTANS nie jest za mały).")