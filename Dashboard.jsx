import StatCard from "./StatCard";

export default function Dashboard() {
  return (
    <div>
      <StatCard title="Total Balance" value="1,250,000" />
      <StatCard title="Income" value="320,000" />
      <StatCard title="Expenses" value="210,000" />
      <StatCard title="Savings" value="110,000" />
    </div>
  );
}