import { useEffect, useState } from "react";

export default function App() {
  const [genre, setGenre] = useState("VTuber");
  const [ranking, setRanking] = useState([]);
  const [hot, setHot] = useState([]);

  useEffect(() => {
    fetch(`http://localhost:8000/ranking/${genre}`)
      .then(res => res.json())
      .then(data => setRanking(data));

    fetch("http://localhost:8000/hot")
      .then(res => res.json())
      .then(data => setHot(data));
  }, [genre]);

  const genres = ["VTuber", "音楽", "スポーツ", "俳優"];

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <h1 className="text-3xl font-bold mb-6">🔥 トレンドランキング</h1>

      {/* HOT */}
      <div className="mb-8">
        <h2 className="text-xl font-semibold mb-3">🔥 HOT（急上昇）</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {hot.map((item, i) => (
            <div key={i} className="bg-white p-4 rounded-2xl shadow">
              <div className="text-lg font-bold">{i + 1}. {item.person}</div>
              <div className="text-sm text-red-500">{item.trend}</div>
              <div className="text-sm">スコア: {item.score.toFixed(1)}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Genre Tabs */}
      <div className="flex gap-2 mb-4">
        {genres.map(g => (
          <button
            key={g}
            onClick={() => setGenre(g)}
            className={`px-4 py-2 rounded-xl ${genre === g ? "bg-black text-white" : "bg-white"}`}
          >
            {g}
          </button>
        ))}
      </div>

      {/* Ranking */}
      <div>
        <h2 className="text-xl font-semibold mb-3">{genre}ランキング</h2>
        <div className="space-y-3">
          {ranking.map((item, i) => (
            <div key={i} className="bg-white p-4 rounded-2xl shadow flex justify-between">
              <div>
                <div className="text-lg font-bold">
                  {i + 1}. {item.person}
                  {item.trend !== "通常" && (
                    <span className="ml-2 text-red-500">🔥</span>
                  )}
                </div>
                <div className="text-sm text-gray-500">{item.trend}</div>
              </div>
              <div className="text-sm">{item.score.toFixed(1)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}