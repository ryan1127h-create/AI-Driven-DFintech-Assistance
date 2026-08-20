const supabase = require('../config/supabase')

// Prospective Student Register
const register = async (userData) => {
  const { email, password, full_name } = userData;

  const { data, error } = await supabase.auth.signUp({
    email,
    password,
  });

  if (error) {
    console.error("SignUp Error:", error);
    throw error;
  }

  const { error: rpcError } =
    await supabase
    .schema("student")
    .rpc("create_user_records", {
      p_user_id: data.user.id,
      p_email: email,
      p_full_name: full_name,
    });

  if (rpcError) {
    console.error("RPC Error:", rpcError);
    throw rpcError;
  }

  return data;
};

const login = async (email, password) => {
  const { data, error } =
    await supabase.auth.signInWithPassword({
      email,
      password,
    });

  if (error) throw error;

  const userId = data.user.id;

  const { data: roleData, error: roleError } =
    await supabase
      .schema('student')
      .from('user_roles')
      .select(`
        role_id,
        roles (
          role_name
        )
      `)
      .eq('user_id', userId);

  if (roleError) throw roleError;

  return {
    session: data.session,
    user: data.user,
    roles: roleData
  };
};


module.exports = {
  register,
  login
};