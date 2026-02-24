import pandas as pd
import folium
from folium.plugins import MarkerCluster
from folium import Element
from datetime import date
import debugpy
from .devices.panel.clustering_panel import add_marker_panel
from .devices.edge_fog.clustering_edge_fog import add_marker_edge_fog
import os
from pathlib import Path
#---------------------------------------------------------------------------------------------------------------------------------------------------------------
#------------------------------------------------------------------To Generate the Density Map------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------------------------------------------

def create_density_map(p):

    # Load the data from the CSV file
    df = pd.read_csv(p.clustering.raw_database.path, sep=';', decimal=',')

    # Center the map at the average location
    print("Centering map...")
    fields = p.clustering.raw_database.fields

    map_center = [df[fields.lat].mean(), df[fields.lon].mean()]
    map_object = folium.Map(location=map_center, zoom_start=12)

    # Add a MarkerCluster to handle large volumes of data efficiently
    marker_cluster = MarkerCluster().add_to(map_object)

    # Add the public lighting points to the cluster
    print("Clustering by density...")
    labels = p.clustering.raw_database.labels
    for _, row in df.iterrows():
        popup_parts = []
        for _, value in labels.items():
            label = getattr(fields,value)
            if label in row:
                popup_parts.append(f"{label}: {row[label]}")
            else:
                print(f"[WARN] Missing label column '{label}' in raw database.")
        popup_text = ", ".join(popup_parts)
        folium.Marker(
            location=[row[fields.lat], row[fields.lon]],
            popup=popup_text
        ).add_to(marker_cluster)


    # Save the map as an HTML file
    print("Generating map...")
    
    # get the file name of p.clustering.raw_database.path
    
    raw_database_filename = Path(p.clustering.raw_database.path).stem
    map_dir = p.clustering.final_path
    os.makedirs(map_dir, exist_ok=True)
    map_file = f"{map_dir}/{raw_database_filename}_density_map.html"
    map_object.save(map_file)
    
    return df

    #-----------------------------------------------------------------------------------------------------------------------------------------------------------
    # Legend (Colors):

    # Orange: Represents large clusters (more than 100 markers).
    # Yellow: Indicates medium-sized clusters (11 to 100 markers).
    # Green: Normally represents small clusters (2 to 10 markers).
    # Blue (marker): It's the point itself (if you click on it you can see more information).

#---------------------------------------------------------------------------------------------------------------------------------------------------------------


#---------------------------------------------------------------------------------------------------------------------------------------------------------------
#------------------------------------------------------------------To Generate the Custered Map-----------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------------------------------------------

def create_clustered_map(p, df_devices):

    # Declare the device creation functions
    create_device_groups = {
        "panel": add_marker_panel,
        "edge_fog": add_marker_edge_fog,
    }
    
    # Define colors for each type
    device_colors = [
        'lightgray', 'black',
        'lightblue', 'darkblue',
        'green', 'darkgreen',
        'lightred', 'orange',
        'red', 'darkred',
        'pink','purple',
        'blue','cadetblue',
        'white', 'gray',
        'beige', 'lightgreen'       
    ]

    palette = [
        ("rgba(128, 128, 128, 1)", "rgba(128, 128, 128, 0.5)", "white"),  # cinza
        ("rgba(100, 149, 237, 1)", "rgba(100, 149, 237, 0.5)", "white"),  # cornflowerblue
        ("rgba(52, 152, 219, 1)", "rgba(52, 152, 219, 0.5)", "white"),    # azul
        ("rgba(231, 76, 60, 1)", "rgba(231, 76, 60, 0.5)", "white"),      # vermelho
        ("rgba(46, 204, 113, 1)", "rgba(46, 204, 113, 0.5)", "black"),    # verde
        ("rgba(155, 89, 182, 1)", "rgba(155, 89, 182, 0.5)", "white"),    # roxo
        ("rgba(241, 196, 15, 1)", "rgba(241, 196, 15, 0.5)", "black"),    # amarelo
        ("rgba(230, 126, 34, 1)", "rgba(230, 126, 34, 0.5)", "black"),    # laranja
        ("rgba(26, 188, 156, 1)", "rgba(26, 188, 156, 0.5)", "black"),    # turquesa
        ("rgba(149, 165, 166, 1)", "rgba(149, 165, 166, 0.5)", "black"),  # cinza claro
        ("rgba(52, 73, 94, 1)", "rgba(52, 73, 94, 0.5)", "white"),        # azul escuro
        ("rgba(192, 57, 43, 1)", "rgba(192, 57, 43, 0.5)", "white"),      # vinho
    ]



    first_key = list(type(p.simulation.devices).model_fields.keys())[0]
    p_fields = getattr(p.simulation.devices, first_key).database.fields

    mymap = folium.Map()

    # Set the option to avoid silent downcasting in future versions (optional)
    pd.set_option('future.no_silent_downcasting', True)

    custom_cluster_colors = "<style>"
    # Simulação da função padrão de criação de ícone do cluster
    lat_sum = 0.0
    lon_sum = 0.0
    lat_count = 0
    lon_count = 0

    for i, (device_name, df_device) in enumerate(df_devices):
        if df_device is None or df_device.empty:
            print(f"Warning: No data available for {device_name}. Skipping its clustering and map generation.")
            continue

        lat_sum += df_device[p_fields.lat].sum()
        lon_sum += df_device[p_fields.lon].sum()
        lat_count += df_device[p_fields.lat].count()
        lon_count += df_device[p_fields.lon].count()
        # create custom icon creation function for each device type
        icon_create_function_by_Type = f"""
            function(cluster) {{
                var childCount = cluster.getChildCount();

                var c = ' marker-cluster-{device_name}';

                return new L.DivIcon({{
                    html: '<div><span>' + childCount + '</span></div>',
                    className: 'marker-cluster' + c,
                    iconSize: new L.Point(40, 40)
                }});
            }}
        """
    
        # create custom CSS for each device type
        custom_cluster_colors = custom_cluster_colors + f"""
        .marker-cluster-{device_name} div {{
            background-color: {palette[i][0]} !important;
        }}
        .marker-cluster-{device_name} {{
            background-color: {palette[i][1]} !important;
            color: {palette[i][2]};
        }}
        """

        
        marker_cluster = MarkerCluster(icon_create_function=icon_create_function_by_Type, name=f'Grupo {device_name}', options = {'maxClusterRadius': 130}).add_to(mymap)
        
        create_fn = create_device_groups.get(device_name)
        create_fn(p, df_device, marker_cluster, device_colors[i*2:(i+1)*2])


    # Ajusta o centro e o zoom depois de adicionar todos os marcadores
    if lat_count > 0 and lon_count > 0:
        mean_lat = lat_sum / lat_count
        mean_lon = lon_sum / lon_count
        mymap.location = [mean_lat, mean_lon]
        mymap.options["zoom"] = 12

    # Salvar o mapa como HTML
    map_dir = p.clustering.final_path
    raw_database_filename = Path(p.clustering.raw_database.path).stem

    os.makedirs(map_dir, exist_ok=True)
    map_file = f"{map_dir}/{raw_database_filename}_clustered_map.html"
    
    # Common additional css style - for all circles
    custom_cluster_colors = custom_cluster_colors + """
    .marker-cluster div {
        border: 2px solid white;
        border-radius: 20px;
        box-shadow: 0 0 10px rgba(0,0,0,0.3);
    }
    </style>
    """

    print(f"Clustered map saved to {map_file}")
    # Adiciona o estilo ao mapa
    mymap.get_root().html.add_child(Element(custom_cluster_colors))

    mymap.save(map_file)
    
#---------------------------------------------------------------------------------------------------------------------------------------------------------------


        
        
        