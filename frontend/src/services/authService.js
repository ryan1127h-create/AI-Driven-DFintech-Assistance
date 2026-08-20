import axios from 'axios';

const API_URL = 'http://localhost:5000/api/auth';

export const register = async (payload) => {
  const response = await axios.post(
    `${API_URL}/register`,
    payload
  );

  return response.data;
};

export const login = async (payload) => {
  const response = await axios.post(
    `${API_URL}/login`,
    payload
  );

  return response.data;
};