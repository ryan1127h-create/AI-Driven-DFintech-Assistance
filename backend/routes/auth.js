const express = require('express');
const router = express.Router();

const authService = require('../services/authService');

router.post('/register', async (req, res) => {
  try {
    const result = await authService.register(req.body);

    res.status(201).json({
      success: true,
      data: result
    });

  } catch (err) {
    console.error("REGISTER ERROR:", err);
    res.status(400).json({
      success: false,
      error: err.message
    });
  }
});

router.post('/login', async (req, res) => {
  try {

    const { email, password } = req.body;

    const result = await authService.login(
      email,
      password
    );

    res.json({
      success: true,
      data: result
    });

  } catch (err) {

    res.status(401).json({
      success: false,
      error: err.message
    });

  }
});

module.exports = router;