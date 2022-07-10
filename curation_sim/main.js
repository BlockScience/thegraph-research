import _ from "lodash";

import {sim_result} from './modules/ohq_sim_1.js';


console.log(JSON.stringify(sim_result, null, 2));

let m0 = {toast: 3, cheese: 4, fast: 8};
let m1 = {toast: 3, cheese: 5};

let my_dict = new Map();

my_dict.set(0, m0);

console.log(my_dict);


my_dict.set(0, {...m0, ...m1})
console.log(my_dict);

console.log(my_dict.get(1));

let list = [1,2,3];
let list2 = list.forEach(x => x + 3);
console.log(list);
console.log(list2);

let list3 = [[1, 2], [2, 200]];
console.log(_.sumBy(list3, 1));