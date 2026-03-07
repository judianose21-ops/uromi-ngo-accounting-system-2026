async function loadDashboard(){

let res = await fetch("/dashboard-data")
let data = await res.json()

document.getElementById("donations").innerText = data.donations
document.getElementById("expenses").innerText = data.expenses
document.getElementById("balance").innerText = data.balance

createChart(data)

}

function createChart(data){

new Chart(document.getElementById("financeChart"),{

type:"bar",

data:{
labels:["Donations","Expenses"],
datasets:[{
label:"Finance",
data:[data.donations,data.expenses]
}]
}

})

}

async function loadLedger(){

let res = await fetch("/ledger")
let rows = await res.json()

let tbody = document.querySelector("#ledgerTable tbody")

tbody.innerHTML=""

rows.forEach(r=>{

let tr=document.createElement("tr")

tr.innerHTML=`
<td>${r[0]}</td>
<td>${r[1]}</td>
<td>${r[2]}</td>
<td>${r[3]}</td>
<td>${r[4]}</td>
`

tbody.appendChild(tr)

})

}

document.getElementById("donationForm").onsubmit=async(e)=>{

e.preventDefault()

await fetch("/add-donation",{

method:"POST",

headers:{"Content-Type":"application/json"},

body:JSON.stringify({

date:don_date.value,
description:don_desc.value,
amount:parseFloat(don_amount.value)

})

})

loadDashboard()
loadLedger()

}

document.getElementById("expenseForm").onsubmit=async(e)=>{

e.preventDefault()

await fetch("/add-expense",{

method:"POST",

headers:{"Content-Type":"application/json"},

body:JSON.stringify({

date:exp_date.value,
description:exp_desc.value,
amount:parseFloat(exp_amount.value)

})

})

loadDashboard()
loadLedger()

}

loadDashboard()
loadLedger()
async function monthlyChart(){

let res = await fetch("/monthly-finance")
let data = await res.json()

let months=[]
let donations=[]
let expenses=[]

data.forEach(r=>{
months.push(r[0])
donations.push(r[1])
expenses.push(r[2])
})

new Chart(document.getElementById("financeChart"),{

type:"line",

data:{
labels:months,
datasets:[
{label:"Donations",data:donations},
{label:"Expenses",data:expenses}
]
}

})

}

monthlyChart()