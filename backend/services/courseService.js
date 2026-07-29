const supabase = require('../config/supabase')

async function getCourses() {
  const { data, error } = await supabase
  .schema('app')
  .from('courses')
  .select('*')

  if (error) {
    throw error
  }

  return data
}

module.exports = {
  getCourses
}
