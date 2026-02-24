import pandas as pd
import os
from .create_maps import *
from .devices.panel.clustering_panel import *
from .devices.edge_fog.clustering_edge_fog import *
import pandas as pd
import numpy as np
from pathlib import Path
import debugpy



def clustering(p):
    
    # Declare the device creation functions
    create_device_groups = {
        "panel": create_panels,
        "edge_fog": create_edges_fogs,
    }
    
    clustering_setup = p.clustering    
    raw_data_path = p.clustering.raw_database.path
    final_path = clustering_setup.final_path
    
    # get only the raw data file name
    raw_data_file_name = os.path.basename(raw_data_path)
    
    # read the raw data file
    df = pd.read_csv(raw_data_path, sep=";", decimal=",")
     
    #---------------------------------Clustering a percentage into panels groups---------------------------------------  
    print("\n" + "-" * 100 + "\n" + "-" * 100)
    print("Starting Clustering...\n")   
    
    # Divide into cells and calculate densities (Returns 2 df. One with density and the other with the entire table)
    points_table = create_clusters(df, p)


    used_percentage = 0
        
    # Get device names sorted by priority
    device_names = sorted(
        (
            (name, getattr(p.clustering.devices, name).priority)
            for name in type(p.clustering.devices).model_fields
        ),
        key=lambda x: x[1], reverse=True
    )

    df_devices = []
    for device_name, _ in device_names:

        device_clustering = getattr(p.clustering.devices, device_name)
        
        print(f"Clustering {device_clustering.percentage * 100}% into {device_name} groups...")

        # Create the panel groups (with branches)
        create_fn = create_device_groups.get(device_name)
        if not create_fn:
            raise ValueError(f"No clustering function registered for device: {device_name}")
        
        points_table, df_device = create_fn(p, points_table, used_percentage)
        
        used_percentage = device_clustering.percentage + used_percentage
        # Save final panel dataset
        
        if df_device is not None and not df_device.empty:
            df_device.to_csv(f"{final_path}/{Path(raw_data_file_name).stem}_only_{device_name}.csv", index=False, sep=';', decimal=',') # Save the result to a CSV file

        df_devices.append([device_name, df_device])
    #--------------------------------------------------------------------------------------------------------------------
    # Final df with All devices clustered 
    devices_path = f"{final_path}/{Path(raw_data_file_name).stem}_all_devices.csv"
    print(f"All clustered devices saved to {devices_path}")
    save_one_single_table(df_devices, devices_path)
            
    # Save final joined dataset
           
    #------------------------------------Create a .html iterative map (panel and edge/fog)------------------------------
    if clustering_setup.generate_clustered_map:

        print(f"\nCreating Clustered Map...")
        # Function to filter groups with n points or less
        
        create_clustered_map(p, df_devices)


        #--------------------------------------------------------------------------------------------------------------------
        print(f"\nClustering completed.")
    return df_devices

    
#-----------------------------------------------------------------------------------------------------------------------------------------------------------------
#------------------------------------------------------ Clustering by Demographic Density -----------------------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------------------------------------------------------

def create_clusters(df, p):
    """
    Creates spatial clusters based on latitude/longitude density and returns:
    1. df with added: lat_cell, lon_cell, cluster_name
    2. density table grouped by (lat_cell, lon_cell)
    """

    # Extract field mappings (dicts, not Pydantic objects!)
    p_raw_fields = p.clustering.raw_database.fields
    p_fields = p.simulation.devices.panel.database.fields

    # Rename input raw columns to simulation panel columns
    df.rename(columns={
        p_raw_fields.id:  p_fields.id,
        p_raw_fields.lat: p_fields.lat,
        p_raw_fields.lon: p_fields.lon,
        p_raw_fields.rated_power: p_fields.rated_power,
        p_raw_fields.rated_voltage: p_fields.rated_voltage,
        p_raw_fields.rated_power_factor: p_fields.rated_power_factor,
    }, inplace=True)

    # Precompute base current from rated values
    df[p_fields.rated_voltage] = pd.to_numeric(df[p_fields.rated_voltage], errors="coerce")
    df[p_fields.rated_power] = pd.to_numeric(df[p_fields.rated_power], errors="coerce")
    df[p_fields.rated_power_factor] = pd.to_numeric(df[p_fields.rated_power_factor], errors="coerce")

    rated_voltage = df[p_fields.rated_voltage].astype(float)
    rated_power = df[p_fields.rated_power].astype(float)
    pf_base = df[p_fields.rated_power_factor].astype(float)
    denom = rated_voltage * np.where(pf_base == 0, 1, pf_base)
    df[p_fields.rated_current] = np.where(denom == 0, 0, rated_power / denom)

    df[p_fields.rated_current] = pd.to_numeric(df[p_fields.rated_current], errors="coerce")

    # Compute grid resolution
    max_range = p.clustering.devices.edge_fog.max_range_km
    lat_step = max_range / 111
    lon_step = max_range / (111 * np.cos(np.deg2rad(df[p_fields.lat].mean())))

    # Compute cells
    df[p_fields.lat_cell] = np.floor(df[p_fields.lat] / lat_step).astype(int)
    df[p_fields.lon_cell] = np.floor(df[p_fields.lon] / lon_step).astype(int)

    # Build cluster name
    df[p_fields.cluster_name] = (
        df[p_fields.lat_cell].astype(str) + "_" +
        df[p_fields.lon_cell].astype(str)
    )

    return df



#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#-------------------------------------------------------------- JOIN PANELS AND EDGES ---------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------

def save_one_single_table(df_devices, devices_path):
    """
    Concatenates df_devices with df_device, ensuring both have the same columns.
    Missing columns are created with None. The "Type" column receives the
    device priority for rows of df_device.
    """
    if df_devices is None:
            return


    frames = []
    all_columns = []
    
    for _, df_device in df_devices:
        
        if df_device is None or df_device.empty:
            continue

        df_device_copy = df_device.copy()
        # Track all columns in a stable order
        for col in df_device_copy.columns:
            if col not in all_columns:
                all_columns.append(col)

        frames.append(df_device_copy)

    if not frames:
        return

    # Align columns across frames
    frames = [df.reindex(columns=all_columns) for df in frames]
    df_device_concat = pd.concat(frames, sort=False).reset_index(drop=True)
    
    df_device_concat.to_csv(devices_path, index=False, sep=';', decimal=',') # Save the result to a CSV file
 
    return






