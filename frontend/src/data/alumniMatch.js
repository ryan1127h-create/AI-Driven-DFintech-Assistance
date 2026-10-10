// TEMPORARY MOCK DATA
// Used only while the Alumni Match database/API is unavailable.
// Once VITE_USE_MOCK_DATA=false and the alumni endpoints are live, delete this
// file and remove its import from frontend/api.js.
export const alumniMatchPhotos = [
  "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?crop=faces&fit=crop&w=320&h=320&q=85",
  "https://images.unsplash.com/photo-1494790108377-be9c29b29330?crop=faces&fit=crop&w=320&h=320&q=85",
  "https://images.unsplash.com/photo-1655249493799-9cee4fe983bb?crop=faces&fit=crop&w=320&h=320&q=85",
  "https://images.unsplash.com/photo-1609436132311-e4b0c9370469?crop=faces&fit=crop&w=320&h=320&q=85",
  "https://images.unsplash.com/photo-1588178454780-441fa5b99fa5?crop=faces&fit=crop&w=320&h=320&q=85",
  "https://images.unsplash.com/photo-1609371497456-3a55a205d5eb?crop=faces&fit=crop&w=320&h=320&q=85",
];

export const alumniMatchData = {
  currentUser: { name: "Emily Chen", role: "Product leader · Class of 2018", photo: alumniMatchPhotos[1] },
  expertiseOptions: ["Blockchain", "Cybersecurity", "Data Analytics", "Data Engineering", "Entrepreneurship", "Finance & Investment", "Machine Learning & AI", "Product & Business", "Quantitative Finance", "Regulation & Governance", "Risk Management", "Software Engineering"],
  alumni: [
    { id: 1, name: "Alex Tan", position: "Senior Software Engineer", company: "Microsoft", expertise: ["Machine Learning & AI", "Software Engineering", "Data Analytics", "Product & Business", "Cybersecurity"], photo: alumniMatchPhotos[0] },
    { id: 2, name: "Sofia Martinez", position: "Product Strategy Lead", company: "Grab", expertise: ["Product & Business", "Entrepreneurship", "Data Analytics"], photo: alumniMatchPhotos[1] },
    { id: 3, name: "Marcus Lee", position: "Quantitative Researcher", company: "J.P. Morgan", expertise: ["Quantitative Finance", "Finance & Investment", "Risk Management"], photo: alumniMatchPhotos[2] },
    { id: 4, name: "Aisha Rahman", position: "Cybersecurity Manager", company: "Deloitte", expertise: ["Cybersecurity", "Regulation & Governance", "Risk Management", "Blockchain"], photo: alumniMatchPhotos[3] },
    { id: 5, name: "Daniel Wong", position: "Data Engineering Lead", company: "AirAsia", expertise: ["Data Engineering", "Software Engineering", "Machine Learning & AI"], photo: alumniMatchPhotos[4] },
    { id: 6, name: "Priya Nair", position: "Venture Partner", company: "500 Global", expertise: ["Entrepreneurship", "Finance & Investment", "Product & Business"], photo: alumniMatchPhotos[5] },
  ],
  incomingRequest: { name: "Noor Aziz", position: "Graduating Computer Science student · Class of 2025", photo: alumniMatchPhotos[0], expertise: ["Machine Learning & AI", "Software Engineering"], note: "Hi Emily, I'm graduating soon and would value your advice on starting a career in AI engineering." },
  sentRequests: [5, 6],
};
