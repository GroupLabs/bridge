import axios from 'axios';

const LOAD_URL = 'http://localhost:8000/load_query';
const SORT_URL = 'http://localhost:8000/sort';
const WS_URL = 'ws://localhost:8000/ws/';

export const uploadFile = (file: File): Promise<void> => {
    console.log('Started');
    return new Promise<void>((resolve, reject) => {
        // Establish WebSocket connection before file upload
        const ws = new WebSocket(`${WS_URL}${file.name}`);

        ws.onopen = async () => {
            console.log('WebSocket connection opened');
            try {
                const formData = new FormData();
                formData.append('file', file);

                await axios.post(LOAD_URL, formData, {
                    headers: {
                        'Content-Type': 'multipart/form-data',
                    },
                });
            } catch (error) {
                console.error('File upload error:', error);
                reject(error);
            }
        };

        ws.onmessage = (event) => {
            console.log(`Received: ${event.data}`);
            // Close the WebSocket connection when the upload is complete
            if (event.data === "Task complete!") {
                ws.close();
                resolve();
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            reject(error);
        };
    });
};

export const getSortedFiles = async (field: string) => {
    try {
        const formData = new FormData();
        formData.append('type', field);

        const response = await axios.post(SORT_URL, formData);
        return response.data;
    } catch (error) {
        console.error('Error getting sorted files:', error);
        throw error;
    }
}
