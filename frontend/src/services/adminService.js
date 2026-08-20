import axios from "axios";

const API_URL = "http://localhost:5000/api/admin";

export const getDepartments = () => {
  return axios.get(`${API_URL}/departments`);
};

export const getStaffRoles = () => {
  return axios.get(`${API_URL}/roles/staff`);
};

export const registerStaff = (payload) => {
  console.log(payload)
  return axios.post(
    `${API_URL}/staff/register`,
    payload
  );
};