import express from 'express';
import cors from 'cors';
import multer from 'multer';
import axios from 'axios';
import crypto from 'crypto';
import fs from 'fs';
import FormData from 'form-data';
import 'dotenv/config';
import { WebSocketServer, WebSocket } from 'ws';

const app = express();
const upload = multer({ dest: 'uploads/' });

app.use(cors({
  origin: ['http://localhost:5173', 'http://localhost:5174'],
  credentials: true,
}));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

const PORT = process.env.PORT || 3001;
const API_GATEWAY_URL = process.env.API_GATEWAY_URL || 'http://localhost:10000';

console.log('API_GATEWAY_URL:', API_GATEWAY_URL);
console.log('KEYCLOAK_URL:', process.env.KEYCLOAK_URL);

let keycloakToken = null;
let tokenExpiresAt = 0;

async function getKeycloakToken() {
  const now = Date.now();
  if (keycloakToken && now < tokenExpiresAt - 60000) {
    return keycloakToken;
  }

  const tokenUrl = `${process.env.KEYCLOAK_URL}/realms/${process.env.KEYCLOAK_REALM}/protocol/openid-connect/token`;
  
  const response = await axios.post(
    tokenUrl,
    new URLSearchParams({
      grant_type: 'client_credentials',
      client_id: process.env.KEYCLOAK_CLIENT_ID,
      client_secret: process.env.KEYCLOAK_CLIENT_SECRET,
    }),
    {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    }
  );

  keycloakToken = response.data.access_token;
  tokenExpiresAt = now + (response.data.expires_in * 1000);
  
  console.log('Got new Keycloak token');
  return keycloakToken;
}

function generateJobId() {
  return crypto.randomUUID();
}

app.post('/api/async/job', upload.single('audio'), async (req, res) => {
  try {
    console.log('Received file:', req.file);
    console.log('Request body:', req.body);
    
    if (!req.file) {
      return res.status(400).json({ error: 'Audio file is required' });
    }

    const sendToTelegram = req.body.send_to_telegram === 'true';
    const telegramUserId = req.body.telegram_user_id?.trim();

    if (sendToTelegram && !telegramUserId) {
      return res.status(400).json({ error: 'Telegram user ID is required when "Send to Telegram" is enabled' });
    }

    const token = await getKeycloakToken();
    const jobId = generateJobId();

    const tokenParts = token.split('.');
    const tokenPayload = JSON.parse(Buffer.from(tokenParts[1], 'base64').toString());
    const userId = tokenPayload.sub || tokenPayload.user_id;

    const fileBuffer = fs.readFileSync(req.file.path);
    const formData = new FormData();
    formData.append('file', fileBuffer, {
      filename: req.file.originalname,
      contentType: req.file.mimetype,
    });
    formData.append('job_id', jobId);
    formData.append('user_id', userId);

    if (sendToTelegram && telegramUserId) {
      const webhookUrl = process.env.TG_WEBHOOK_URL || 
        (process.env.NODE_ENV === 'production' ? 'http://tg-webhook-test:10050/webhook' : 'http://localhost:10050/webhook');
      const appToken = process.env.APP_TOKEN || 'hardcoded_secret_token_for_webhook_auth';
      formData.append('webhook_url', webhookUrl);
      formData.append('webhook_method', 'POST');
      formData.append('webhook_headers', JSON.stringify({ 
        'X-User-ID': telegramUserId,
        'X-App-Token': appToken
      }));
      console.log('Added webhook URL:', webhookUrl, 'for user:', telegramUserId, 'app_token:', appToken);
    }

    console.log('Sending to API Gateway:', `${API_GATEWAY_URL}/api/async/job`);
    
    const response = await axios.post(
      `${API_GATEWAY_URL}/api/async/job`,
      formData,
      {
        headers: {
          'Authorization': `Bearer ${token}`,
          ...formData.getHeaders(),
        },
        maxContentLength: Infinity,
        maxBodyLength: Infinity,
      }
    );

    console.log('API Gateway response:', response.data);
    
    let createdJobId;
    if (response.data.job_id) {
      createdJobId = response.data.job_id;
    } else if (response.data.id) {
      createdJobId = response.data.id;
    } else if (response.data.jobs && response.data.jobs.length > 0) {
      createdJobId = response.data.jobs[0].id || response.data.jobs[0].job_id;
    } else {
      createdJobId = jobId;
    }
    
    console.log('Created job ID:', createdJobId);
    res.json({ job_id: createdJobId, status: response.data.status || 'in_progress' });
  } catch (error) {
    console.error('Error creating job:', error.message);
    console.error('Error details:', error.response?.data);
    res.status(500).json({ error: error.message, details: error.response?.data });
  }
});

app.get('/api/async/job/:job_id', async (req, res) => {
  try {
    const token = await getKeycloakToken();
    const { job_id } = req.params;
    
    console.log('Checking job status:', job_id);
    
    const response = await axios.get(
      `${API_GATEWAY_URL}/api/async/job/${job_id}`,
      {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        responseType: 'text',
      }
    );

    let data;
    const contentType = response.headers['content-type'];
    
    if (contentType && contentType.includes('application/json')) {
      data = JSON.parse(response.data);
    } else {
      try {
        data = JSON.parse(response.data);
      } catch {
        data = { result: response.data };
      }
    }
    
    console.log('Job status response:', data);
    res.json(data);
  } catch (error) {
    console.error('Error getting job:', error.message);
    console.error('Status code:', error.response?.status);
    console.error('Response data:', error.response?.data);
    
    if (error.response?.status === 404) {
      return res.status(404).json({ error: 'Job not found', job_id: req.params.job_id });
    }
    
    res.status(500).json({ error: error.message, details: error.response?.data });
  }
});

app.listen(PORT, () => {
  console.log(`Backend server running on port ${PORT}`);
});

const wss = new WebSocketServer({ port: PORT + 1 });
console.log(`WebSocket server running on port ${PORT + 1}`);

wss.on('connection', async (ws) => {
  console.log('New WebSocket client connected');

  let gatewayWs = null;
  let token = null;

  try {
    token = await getKeycloakToken();
    const gatewayUrl = API_GATEWAY_URL.replace('http://', 'ws://').replace('https://', 'wss://') + '/api/sync/job';

    console.log('Connecting to API Gateway:', gatewayUrl);

    gatewayWs = new WebSocket(gatewayUrl, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });

    gatewayWs.on('open', () => {
      console.log('Connected to API Gateway');
      ws.send(JSON.stringify({ status: 'ready' }));
    });

    gatewayWs.on('message', (data) => {
      console.log('Received from gateway:', data.toString().substring(0, 200));
      ws.send(data.toString());
    });

    gatewayWs.on('error', (error) => {
      console.error('Gateway WebSocket error:', error.message);
      ws.send(JSON.stringify({ type: 'error', error: error.message }));
    });

    gatewayWs.on('close', () => {
      console.log('Gateway WebSocket closed');
      ws.close();
    });

  } catch (error) {
    console.error('Failed to connect to gateway:', error.message);
    ws.send(JSON.stringify({ type: 'error', error: error.message }));
    ws.close();
    return;
  }

  ws.on('message', (data) => {
    if (gatewayWs && gatewayWs.readyState === 1) {
      console.log('Forwarding to gateway:', data.toString().substring(0, 100));
      gatewayWs.send(data.toString());
    }
  });

  ws.on('close', () => {
    console.log('Client disconnected');
    if (gatewayWs) {
      gatewayWs.close();
    }
  });
});