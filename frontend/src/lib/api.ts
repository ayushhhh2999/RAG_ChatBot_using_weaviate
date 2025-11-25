const API_BASE_URL = "http://localhost:8000";

export async function getDocuments() {
  return await fetch(`${API_BASE_URL}/documents`).then(r => r.json());
}

export async function findCorruptedChunks() {
  return await fetch(`${API_BASE_URL}/find_corrupted-chunks`).then(r => r.json());
}

export async function cleanDatabase() {
  return await fetch(`${API_BASE_URL}/clean-database`, {
    method: "DELETE"
  }).then(r => r.json());
}
