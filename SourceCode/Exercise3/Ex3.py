import pandas as pd
import numpy as np
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.impute import SimpleImputer

pd.set_option('future.no_silent_downcasting', True)

script_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(script_dir, "..", "Exercise1", "results.csv")
print(f"Attempting to load file from: {file_path}")

df = pd.read_csv(file_path, encoding='utf-8')

percent_cols = ['Won%', 'Save%', 'CS%', 'Pen Save%']
for col in percent_cols:
    if col in df.columns:
        df[col] = (
            df[col]
            .astype(str)
            .replace('N/a', np.nan)
            .str.replace(r'[^\d.]', '', regex=True)
            .pipe(pd.to_numeric, errors='coerce')
            / 100
        )

if 'GA90' in df.columns:
    df['GA90'] = pd.to_numeric(df['GA90'], errors='coerce')

non_stats_columns = ['First Name', 'Nation', 'Team', 'Position', 'Age', 'Match played', 'Starts', 'Minutes']
stats_columns = [col for col in df.columns if col not in non_stats_columns]

for stat in stats_columns:
    df[stat] = pd.to_numeric(df[stat], errors='coerce')

imputer = SimpleImputer(strategy='mean')
data_imputed = imputer.fit_transform(df[stats_columns])

scaler = StandardScaler()
scaled_data = scaler.fit_transform(data_imputed)

inertia = []
silhouette_scores = []
K_range = range(2, 21)
for k in K_range:
    kmeans = KMeans(n_clusters=k, random_state=42)
    kmeans.fit(scaled_data)
    inertia.append(kmeans.inertia_)
    silhouette_scores.append(silhouette_score(scaled_data, kmeans.labels_))

optimal_k = K_range[np.argmax(silhouette_scores)]
print(f"Optimal number of clusters (based on silhouette score): {optimal_k}")

kmeans = KMeans(n_clusters=optimal_k, random_state=42)
clusters = kmeans.fit_predict(scaled_data)

pca = PCA(n_components=2)
principal_components = pca.fit_transform(scaled_data)

explained_variance_ratio = pca.explained_variance_ratio_
print(f"Explained variance ratio by PCA components: {explained_variance_ratio}")

plt.figure(figsize=(10, 6))
scatter = plt.scatter(principal_components[:, 0], principal_components[:, 1], 
                     c=clusters, cmap='viridis', alpha=0.6)
plt.xlabel('Principal Component 1')
plt.ylabel('Principal Component 2')
plt.title(f'Player Clusters (K={optimal_k})')
plt.colorbar(scatter)
plt.savefig(os.path.join(script_dir, 'player_clusters.png'), bbox_inches='tight')
plt.close()

plt.figure(figsize=(12, 5))
plt.subplot(1, 2, 1)
plt.plot(K_range, inertia, 'bx-')
plt.xlabel('Number of clusters')
plt.ylabel('Inertia')
plt.title('Elbow Method')
plt.subplot(1, 2, 2)
plt.plot(K_range, silhouette_scores, 'rx-')
plt.xlabel('Number of clusters')
plt.ylabel('Silhouette Score')
plt.title('Silhouette Analysis')
plt.tight_layout()
plt.savefig(os.path.join(script_dir, 'clustering_analysis.png'), bbox_inches='tight')
plt.close()

with open(os.path.join(script_dir, 'clustering_explanation.txt'), 'w', encoding='utf-8') as f:
    f.write("=== Phân tích phân cụm cầu thủ ===\n\n")
    f.write("1. Số lượng cụm tối ưu:\n")
    f.write(f"Số lượng cụm tối ưu được chọn là {optimal_k}, dựa trên điểm Silhouette cao nhất.\n")
    f.write("Lý do chọn số cụm này:\n")
    f.write("- Phương pháp Elbow Method cho thấy inertia giảm mạnh ở một số giá trị k nhỏ, nhưng không luôn rõ ràng để xác định điểm 'khuỷu tay' chính xác.\n")
    f.write(f"- Điểm Silhouette đo lường mức độ gắn kết và tách biệt của các cụm. Giá trị cao nhất tại k={optimal_k} cho thấy các cầu thủ được phân cụm tốt, với sự tương đồng cao trong cụm và khác biệt rõ ràng giữa các cụm.\n")
    f.write(f"- Số cụm {optimal_k} hợp lý trong bối cảnh bóng đá, vì các cầu thủ có thể được chia thành các nhóm như thủ môn, hậu vệ, tiền vệ, tiền đạo, hoặc các vai trò chuyên biệt hơn (ví dụ: tiền vệ phòng ngự, tiền đạo cánh).\n")
    f.write("\n2. Nhận xét về kết quả phân cụm:\n")
    f.write("- Kết quả phân cụm được trực quan hóa trong 'player_clusters.png', sử dụng PCA để giảm chiều dữ liệu xuống 2 chiều. Mỗi điểm đại diện cho một cầu thủ, và màu sắc biểu thị cụm.\n")
    f.write(f"- Tỷ lệ phương sai giải thích bởi hai thành phần chính là {explained_variance_ratio[0]:.2f} và {explained_variance_ratio[1]:.2f}, tổng cộng {sum(explained_variance_ratio):.2f}. Giá trị này cho thấy mức độ thông tin được giữ lại sau khi giảm chiều. Nếu tỷ lệ thấp (<0.7), một số thông tin có thể bị mất, nhưng biểu đồ vẫn hữu ích để trực quan hóa.\n")
    f.write("- Các cụm có thể đại diện cho các kiểu cầu thủ khác nhau, ví dụ:\n")
    f.write("  + Cụm chứa các thủ môn, với các chỉ số như Save%, CS% cao và các chỉ số tấn công thấp.\n")
    f.write("  + Cụm chứa các tiền đạo, với Goals, xG, SoT% cao.\n")
    f.write("  + Cụm chứa các tiền vệ, với PrgP, PrgR, hoặc Passes Completed cao.\n")
    f.write("- Biểu đồ phân cụm cho thấy sự tách biệt giữa các cụm. Nếu các điểm dữ liệu chồng chéo, điều này có thể do dữ liệu phức tạp hoặc số cụm chưa tối ưu hoàn toàn.\n")
    f.write("- Việc sử dụng SimpleImputer để điền giá trị thiếu bằng giá trị trung bình có thể ảnh hưởng đến tính chính xác của cụm, đặc biệt với các thống kê không áp dụng (như Save% cho không phải thủ môn). Trong tương lai, có thể xem xét loại bỏ các cột không liên quan theo vị trí cầu thủ trước khi phân cụm.\n")
    f.write("- Kết quả phân cụm có thể được sử dụng để phân tích chiến thuật, ví dụ: xác định các cầu thủ có phong cách chơi tương tự hoặc tìm kiếm cầu thủ thay thế dựa trên cụm.\n")
