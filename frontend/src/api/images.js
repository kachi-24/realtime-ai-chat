export async function uploadImage(file, apiFetch) {
  const formData = new FormData();

  formData.append("file", file);

  const response = await apiFetch(
    "/images/upload",
    {
      method: "POST",
      body: formData,
    }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      data.detail || "Image upload failed."
    );
  }

  return data;
}