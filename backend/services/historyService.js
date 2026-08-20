const supabase = require('../config/supabase')

// 按 user_id 拉回某用户的聊天历史。
// 用 supabase-js 的「嵌套 select」连表:查 conversations,并把每个对话下面的
// messages 一起嵌套查出来(靠我们建的 conversation_id 外键自动连,等价于 SQL 的 join)。
async function getUserHistory(userId) {
  const { data, error } = await supabase
    .schema('student')                       // 表在 student schema(不是默认的 public)
    .from('conversations')                    // 从对话表出发
    .select(
      'conversation_id, title, started_at, ' +
      'messages(sender_type, message_text, created_at)'   // 嵌套:每个对话下的消息
    )
    .eq('user_id', userId)                    // 只要这个用户的
    .order('started_at', { ascending: true }) // 对话按时间排
    .order('created_at', { referencedTable: 'messages', ascending: true }) // 消息也按时间排

  if (error) {
    throw error
  }

  return data
}

module.exports = {
  getUserHistory
}
