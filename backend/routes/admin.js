const express = require("express");
const router = express.Router();

const {  getDepartments, getStaffRoles, registerStaff } = require("../services/adminService");

router.get("/departments", async (req, res) => {
  try {
    const departments = await getDepartments();

    res.json(departments);
  } catch (error) {
    console.error("Departments Error:", error);

    res.status(500).json({
      message: error.message,
    });
  }
});

router.get("/roles/staff", async (req, res) => {
  try {
    const roles = await getStaffRoles();

    res.json(roles);
  } catch (error) {
    console.error("Roles Error:", error);

    res.status(500).json({
      message: error.message,
    });
  }
});

router.post("/staff/register", async (req, res) => {
  try {
    const staff = await registerStaff(req.body);

    res.status(201).json(staff);
  } catch (error) {
    res.status(500).json({
      message: error.message,
    });
  }
});

module.exports = router;