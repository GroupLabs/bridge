import axios from 'axios';

export default async function handler(req, res) {
  if (req.method === 'POST') {
    const formData = new FormData();
    formData.append('file', req.files.file);

    try {
      const response = await axios.post('http://localhost:8000/parse', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      res.status(200).json(response.data);
    } catch (error) {
      res.status(500).json({ error: error.message });
    }
  } else {
    res.status(405).json({ error: 'Method not allowed' });
  }
}