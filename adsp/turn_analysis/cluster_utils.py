import sys
# add parent directory and its parent to sys.path so that python finds the modules
sys.path.append('..')

from typing import Tuple, List, Dict
from datetime import datetime

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import ticker
from matplotlib.lines import Line2D
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler
from db_utils import get_rect_to_rect_data
import contextily as cx

plt.rcParams.update({
    "figure.facecolor":  'white', 
    "axes.facecolor":    'white', 
    "savefig.facecolor": 'white', 
})

def get_path_rotated(df_simra: pd.DataFrame) -> Tuple[np.float, np.float]:
    # rotate vector by 90 degrees clockwise
    #    (x, y)     -> (y, -x)
    # =  (lon, lat) -> (lat, -lon

    lat_start = df_simra.iloc[0].lat
    lat_end = df_simra.iloc[-1].lat

    delta_lat = lat_end - lat_start

    lon_start = df_simra.iloc[0].lon
    lon_end = df_simra.iloc[-1].lon

    delta_lon = lon_end - lon_start

    path_rotated_lon_unnormalized = delta_lat
    path_rotated_lat_unnormalized = (-1) *  delta_lon

    path_rotated_lon = path_rotated_lon_unnormalized / np.sqrt(path_rotated_lon_unnormalized**2+ path_rotated_lat_unnormalized**2)
    path_rotated_lat = path_rotated_lat_unnormalized / np.sqrt(path_rotated_lon_unnormalized**2+ path_rotated_lat_unnormalized**2)

    # return path_rotated_lon, path_rotated_lat
    return path_rotated_lat, path_rotated_lon

def get_off_center(df_simra_grouped: pd.DataFrame, df_simra: pd.DataFrame, path_rotated: Tuple[np.float, np.float]) -> np.ndarray:
    off_center = []
    df_simra_grouped_ = df_simra_grouped.reset_index()
    for filename in df_simra_grouped_['filename']:
        projections = []
        x, y = path_rotated
        x_norm = x / np.sqrt(x**2 + y**2)
        y_norm = y / np.sqrt(x**2 + y**2)
        for lat, lon in zip(df_simra[df_simra['filename'] == filename]['lat'], df_simra[df_simra['filename'] == filename]['lon']):
            projection = (lat * x_norm) + (lon * y_norm)
            projections.append(projection)
        off_center.append(np.max(projections))

    return np.array(off_center)


def min_max_scale_features(features: Dict[str, np.ndarray]):
    Scaler = MinMaxScaler()
    return {feature_name: Scaler.fit_transform(feature_values.reshape(-1, 1))
            for feature_name, feature_values in features.items()}


def cluster_with_kmeans(features: Dict[str, np.ndarray], turn_series: pd.Series, n_cluster: int = 2,  plot: bool = True, **kwargs) -> np.ndarray:

    intersection_number = turn_series['intersection number']
    name = turn_series['name']
    direction = turn_series['direction']
    
    
    kmeans = KMeans(n_clusters=n_cluster, random_state=0)

    feature_names = list(features.keys())
    features = list(features.values())
    features_combined = np.hstack(features)
    cluster_labels = kmeans.fit_predict(features_combined)
    cluster_centers = kmeans.cluster_centers_

    # does only work with n_cluster = 2
    colors = ['blue' if label == 0 else 'orange' for label in cluster_labels]
            
    if plot and len(features) == 2:
        plt.scatter(features_combined[:,0], features_combined[:,1], c=colors)
        plt.scatter(cluster_centers[:,0], cluster_centers[:,1], color='red', s=100)
        plt.xlabel(f'{feature_names[0]} (min-max-scaled)')
        plt.ylabel(f'{feature_names[1]} (min-max-scaled)')
    if plot and len(features) == 1:
        sns.stripplot(x=[x_ for x_, label in zip(features[0], cluster_labels) if label == 0], color='blue')
        sns.stripplot(x=[x_ for x_, label in zip(features[0], cluster_labels) if label == 1], color='orange')
        sns.stripplot(x=cluster_centers, color='red', size=10, jitter=False)
        plt.xlabel(f'{feature_names[0]} (min-max-scaled)')
    
    
    plt.title(f'intersection {intersection_number}: \n{name} \ndirection: {direction}')
    plt.savefig(f'images/k-means_{intersection_number}_{direction}.png', transparent=True, bbox_inches='tight')
    
    plt.show()

    return cluster_labels


def plot_ride_paths(df_simra: pd.DataFrame, cluster_labels: np.ndarray, turn_series: pd.Series, rides: int, fraction_cluster_1: np.ndarray, **kwargs):
    
    intersection_number = turn_series['intersection number']
    name = turn_series['name']
    direction = turn_series['direction']

    if 'figsize_rides' in kwargs:
        figsize_rides = kwargs['figsize_rides']
    else:
        figsize_rides = (12, 12)
    fig, ax = plt.subplots(figsize=figsize_rides)

    colors = ['blue', 'orange']

    df_simra_grouped = df_simra.groupby('filename')
    for i, ride_group_name in enumerate(df_simra_grouped.groups):
        df_ride_group = df_simra_grouped.get_group(ride_group_name)
        ax.plot(df_ride_group.lon, df_ride_group.lat, color=colors[cluster_labels[i]], linewidth=1)

        # df_ride_group_vec = df_simra_grouped_vec[df_simra_grouped_vec.filename == ride_group_name]
        # vec_rot_lon = [lon_start, lon_start + path_rotated_lon]
        # vec_rot_lat = [lat_start, lat_start + path_rotated_lat]
        # ax.plot(vec_rot_lon, vec_rot_lat, color='green')

        # projection_point_lon = np.float(path_rotated_lon) * df_ride_group_vec['max_projection']
        # projection_point_lat = np.float(path_rotated_lat) * df_ride_group_vec['max_projection']

        # print(projection_point_lon, projection_point_lat)
        # ax.scatter([projection_point_lon], [projection_point_lat], color='red', s=50)

    # ax.set_xlim(min(df_simra.lon), max(df_simra.lon))
    # ax.set_ylim(min(df_simra.lat), max(df_simra.lat))

    ax.xaxis.set_major_locator(ticker.LinearLocator(4))
    ax.xaxis.set_major_formatter(ticker.ScalarFormatter(useOffset=False))
    ax.yaxis.set_major_locator(ticker.LinearLocator(4))
    ax.yaxis.set_major_formatter(ticker.ScalarFormatter(useOffset=False))
    ax.set_xlabel('Longitude in decimal degrees')
    ax.set_ylabel('Latitude in decimal degrees')

    cx.add_basemap(ax, crs='EPSG:4326', source=cx.providers.Stamen.Toner)

    fraction_cluster_1_percentage = round(100*fraction_cluster_1,2)
    lines = [Line2D([0],[0], color = colors[0]),
                Line2D([0],[0], color = colors[1])]
    labels = ['cluster 1: '+ str(fraction_cluster_1_percentage)+'\%',
                'cluster 2: '+ str(round(100-fraction_cluster_1_percentage,2))+'\%']
    plt.legend(lines, labels)

    ax.set_aspect(1.7)

    plt.title(f'intersection {intersection_number}:\n{name} \ndirection: {direction}')
    plt.savefig(f'images/clustered_rides_{intersection_number}_{direction}.png', transparent=True)    
    plt.show()


def cluster(df_simra: pd.DataFrame, turn_series, **kwargs):
    df_simra_grouped = df_simra.groupby('filename').agg({'dist': 'sum'})
    distances = np.array(df_simra_grouped.dist)

    path_rotated = get_path_rotated(df_simra)
    off_center = get_off_center(df_simra_grouped, df_simra, path_rotated)

    features = {'off center': off_center, 'distances': distances}
    features_scaled = min_max_scale_features(features)

    cluster_labels = cluster_with_kmeans(features_scaled, turn_series)
    
    fraction_cluster_1 = 1 - cluster_labels.sum() / len(cluster_labels)

    rides = df_simra_grouped.shape[0]

    plot_ride_paths(df_simra, cluster_labels, turn_series, rides, fraction_cluster_1 , **kwargs)

    return fraction_cluster_1, rides


def analyse_df_for_faulty_entries(df_simra, show_faulty_entries = False):
    
    # Some entries contain nans, or no speed, even though a distance is given. Inspect further. Option for filtering or preprocessing.

    faulty_entries = df_simra[((df_simra.velo == 0) | (df_simra.velo.isna())) & (df_simra.dist != 0.0)]

    n_entries = len(df_simra)
    n_faulty_entries = len(faulty_entries) 
    percentage_faulty = n_faulty_entries / n_entries * 100

    print(f'Number of faulty rows (velocity is nan or zero even though distance is given): {n_faulty_entries}')
    print(f'Total rows: {n_entries}')
    print(f'Share of faulty rows: {round(percentage_faulty,2)}%.')

    if show_faulty_entries: display(faulty_entries)


def return_cluster_results_and_plot_path(turn_series, end_date_str = '2099-01-01 00:00:00', **kwargs):
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d %H:%M:%S')
    df_simra = get_rect_to_rect_data(turn_series['start_rect_coords'], turn_series['end_rect_coords'],
        exclude_coords = turn_series['exclude_coords'])
    if df_simra is None:
        print('No rides')
        return None, None
    # if only 1 ride, not possible to cluster
    if len(set(df_simra['filename'])) == 1:
        fraction_cluster_1 = 1
        plot_ride_paths(df_simra, [0], fraction_cluster_1=fraction_cluster_1, rides=1, turn_series = turn_series, **kwargs)
        return 1, 1
    if 'analyse_for_faulty_entries' in kwargs: analyse_df_for_faulty_entries(df_simra)
    share_cluster_1, rides = cluster(df_simra, turn_series, **kwargs)
    return share_cluster_1, rides






