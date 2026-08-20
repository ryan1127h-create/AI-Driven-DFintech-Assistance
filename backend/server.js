const express = require('express')
const cors = require('cors')

const app = express()

app.use(cors())
app.use(express.json())

app.use('/api/auth', require('./routes/auth'));
app.use('/api/courses', require('./routes/courses'))
app.use('/api/history', require('./routes/history'))
app.use('/api/admin', require('./routes/admin'))

app.listen(5000, () => {
  console.log('Server running on port 5000')
})