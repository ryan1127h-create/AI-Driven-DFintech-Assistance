const express = require('express')
const router = express.Router()

const { getUserHistory } = require('../services/historyService')

// GET /api/history?user_id=xxx  → 返回该用户的对话(每个对话内嵌它的消息)
router.get('/', async (req, res) => {
  const userId = req.query.user_id

  if (!userId) {
    return res.status(400).json({ message: 'user_id is required' })
  }

  try {
    const history = await getUserHistory(userId)
    res.json(history)
  } catch (error) {
    res.status(500).json({
      message: error.message
    })
  }
})

module.exports = router
