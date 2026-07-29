const express = require('express')
const router = express.Router()

const { getCourses } = require('../services/courseService')

router.get('/', async (req, res) => {
  try {
    const courses = await getCourses()
    res.json(courses)
  } catch (error) {
    res.status(500).json({
      message: error.message
    })
  }
})

module.exports = router
