
const empFuse = new Fuse(empNumbers, {
keys: ['name'],
threshold: 0.3
});

const loginFuse = new Fuse(loginInfo, {
keys: ['name'],
threshold: 0.3
}



function findUserInfo(inputName) {
const name = inputName.toUpperCase();

const empMatch = empFuse.search(name);
const loginMatch = loginFuse.search(name);

const empId = empMatch.length > 0 ? empMatch[0].item.empId : null;
const username = loginMatch.length > 0 ? loginMatch[0].item.username : null;

return {
    empId: empId || "Not found",
    username: username || "Not found"
};
}