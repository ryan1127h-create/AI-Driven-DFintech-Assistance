const supabase = require('../config/supabase')

const getDepartments = async () => {
  const { data, error } = await supabase
    .schema("student")
    .from("departments")
    .select("department_id, department_name")
    .order("department_name");

  if (error) throw error;

  return data;
};

const getStaffRoles = async () => {
  const { data, error } = await supabase
    .schema("student")
    .from("roles")
    .select("role_id, role_name")
    .eq("role_type", "Staff")
    .order("role_name");

  if (error) throw error;

  return data;
};

const registerStaff = async ({
  full_name,
  email,
  password,
  employee_no,
  department_id,
  job_title,
  role_id,
}) => {

  console.log("admin:", full_name, role_id,  email,
  password,
  employee_no,
  department_id,
  job_title,)
  try {
    // validation
    if (
      !full_name ||
      !email ||
      !password ||
      !employee_no ||
      !department_id ||
      !job_title
    ) {
      throw new Error("Missing required fields");
    }

    // Create Auth User
    const {
      data: authData,
      error: authError,
    } = await supabase.auth.createUser({
      email,
      password,
      email_confirm: true,
    });

    if (authError) {
      throw authError;
    }

    const userId = authData.user.id;
    console.log("Auth user:", userId)

    // Insert Users
    const { error: userError } = await supabase
      .schema("student")
      .from("users")
      .insert({
        user_id: userId,
        email,
        full_name,
        account_status: "Active",
      });

    if (userError) {
      throw userError;
    }

    // Insert Staff
    const { error: staffError } = await supabase
      .schema("student")
      .from("staff")
      .insert({
        user_id: userId,
        department_id,
        employee_no,
        job_title,
      });

    if (staffError) {
      throw staffError;
    }

    // Insert Roles
    if (role_id) {
      const { error: roleError } = await supabase
        .schema("student")
        .from("user_roles")
        .insert({
          user_id: userId,
          role_id,
        });

      if (roleError) {
        throw roleError;
      }
    }

    return {
      success: true,
      message: "Staff registered successfully",
      user_id: userId,
    };

  } catch (error) {
    console.error("registerStaff:", error);
    throw error;
  }
};



module.exports = {
  getDepartments,
  getStaffRoles,
  registerStaff,
};