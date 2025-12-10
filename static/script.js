// static/script.js

function togglePasswordInput() {
    // 取得目前選中的模式
    const mode = document.querySelector('input[name="pw_mode"]:checked').value;
    const inputField = document.getElementById('manual_pw');
    
    // 如果是手動，顯示輸入框；否則隱藏並清空
    if (mode === 'manual') {
        inputField.style.display = 'block';
    } else {
        inputField.style.display = 'none';
        inputField.value = ''; 
    }
}

async function submitUser() {
    const username = document.getElementById('username').value;
    const role = document.getElementById('role').value;
    const pwMode = document.querySelector('input[name="pw_mode"]:checked').value;
    const manualPw = document.getElementById('manual_pw').value;

    if(!username) {
        alert("❌ 請輸入帳號");
        return;
    }

    try {
        // 發送資料給後端
        const response = await fetch('/api/create_user', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username: username,
                role: role,
                pw_mode: pwMode,
                manual_pw: manualPw
            })
        });

        const result = await response.json();

        if (result.success) {
            let msg = `✅ 帳號 [ ${username} ] 建立成功！`;
            
            if (result.mode === 'random') {
                msg += `\n\n🔑 隨機密碼為： ${result.new_password}\n\n(請務必複製此密碼給使用者)`;
            } else {
                msg += `\n\n🔑 密碼已設定為手動輸入的值。`;
            }
            
            alert(msg);
            location.reload(); // 重新整理頁面以顯示新列表
        } else {
            alert("❌ 錯誤: " + result.message);
        }

    } catch (error) {
        console.error('Error:', error);
        alert("系統發生錯誤，請檢查後台日誌。");
    }
}