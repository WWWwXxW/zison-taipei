# 自送台北（zison-taipei）

免費、可上傳的靜態網站：搜尋台北「餐廳官方外送／宅配」通道。  
品牌名：**自送台北**。純 HTML／CSS／JS，不需 `npm build`。

倉庫：https://github.com/WWWwXxW/zison-taipei

## 本機預覽

任選一種：

```bash
# Python 3
cd zison-taipei-site   # 或解壓後的資料夾
python3 -m http.server 8080
# 瀏覽器開啟 http://127.0.0.1:8080/
```

或直接用瀏覽器開啟 `index.html`（部分瀏覽器對本地檔案的模組限制較少，本站用相對路徑 script，一般可直接開）。

## 上傳到 GitHub（Web UI，免 Cursor Pro）

1. 開啟 https://github.com/WWWwXxW/zison-taipei （空倉庫亦可）。
2. 若倉庫完全空白，點 **Add file → Upload files**。
3. 把本資料夾（或 zip 解壓後）**所有檔案**拖進去，建議放在倉庫**根目錄**：
   - `index.html`
   - `about.html`
   - `detail.html`
   - `style.css`
   - `app.js`
   - `data.js`
   - `restaurants.json`
   - `README.md`
4. Commit 訊息可寫：`Publish 自送台北 static site`，然後 **Commit changes**。
5. （可選）Settings → Pages → Build and deployment → Source 選 **Deploy from a branch**，Branch 選 `main`／`/`，儲存後數分鐘即可用 `https://wwwwxxw.github.io/zison-taipei/` 之類網址開啟。

也可上傳整包 zip 後在 GitHub 網頁解不開——請解壓後上傳**檔案**，不要只丟一個 zip。

## 可選：Vercel 靜態託管

1. 登入 [vercel.com](https://vercel.com)，**Import** 上述 GitHub 倉庫。
2. Framework Preset 選 **Other**，Build Command 留空，Output Directory 留空（根目錄即靜態檔）。
3. Deploy。之後 push 到 `main` 會自動更新。

## 檔案說明

| 檔案 | 用途 |
|------|------|
| `index.html` | 搜尋、行政區／料理篩選、店家卡片 |
| `about.html` | 目錄模式說明（無餐廳註冊、官方通道下單） |
| `detail.html?id=` | 單店詳情（query param） |
| `data.js` | `window.RESTAURANTS` 資料 |
| `restaurants.json` | 同內容 JSON，方便之後改資料 |
| `app.js` / `style.css` | 前端邏輯與樣式 |

欄位含可選 `featured: false`（日後贊助露出）與 `chain: true`（全國／大型連鎖）。缺電話或網址時不會虛構，該欄直接省略。

## 資料來源

- 主要：ChatGPT handoff `CONFIRMED_RESTAURANTS.md`（約 91 家已確認）
- 次要合併：`taipei-own-delivery-batch1.md`（Scout，去重後併入）

條件與連結可能變動；下單前請以店家官方頁為準。
