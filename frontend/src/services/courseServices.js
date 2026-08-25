export async function getCourses() {
  const response = await fetch(
    'http://localhost:5000/api/courses'
  )
  return response.json()
}