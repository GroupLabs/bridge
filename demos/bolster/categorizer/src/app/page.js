'use client'
import { Fragment, useState } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { v4 as uuidv4 } from 'uuid';


export default function Home() {
  const [people, setPeople] = useState([
    {
      id: uuidv4(), // generates a unique id
      name: 'Light Fixtures',
      title: 'Electrical',
      price: '$15.00'
    },
    {
      id: uuidv4(), // generates a unique id
      name: 'Sink',
      title: 'Plumbing',
      price: '$15.00'
    },
    {
      id: uuidv4(), // generates a unique id
      name: 'Shower',
      title: 'Plumbing',
      price: '$15.00'
    },
    {
      id: uuidv4(), // generates a unique id
      name: 'Washing Machine',
      title: 'Appliance',
      price: '$15.00'
    },

  ]);
  const [open, setOpen] = useState(false);
  const [selectedPerson, setSelectedPerson] = useState(null);
  const handleEdit = (person) => {
    setSelectedPerson({ ...person });
    setOpen(true);
  };

  const updatePerson = (id, newName, newCategory, newPrice) => {
    const updatedPeople = people.map(person => {
      if (person.id === id) {
        return {...person, name: newName, title: newCategory, price: newPrice};
      }
      return person;
    });
    setPeople(updatedPeople);
  };

  return (
    <div className="px-4 sm:px-6 lg:px-8">
          <div className="border-b border-gray-200 pb-5 mt-8">
      <h3 className="text-base font-semibold leading-6 text-gray-900">Demonstration</h3>
      <p className="mt-2 max-w-4xl text-sm text-gray-500">
        In this demonstration, we utilize a language model to determine the similarity between objects and their 
        respective categories. The language model functions like a database, returning categories based on its semantic 
        “understanding” of words. The primary objective is to minimize the model’s latency to ensure its practical usability.
      </p>
    </div>
      <div className="mt-8 flow-root">
        <div className="-mx-4 -my-2 overflow-x-auto sm:-mx-6 lg:-mx-8">
            <div className="inline-block min-w-full py-2 align-middle sm:px-6 lg:px-8">
                <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 sm:rounded-lg">
                    <table className="min-w-full divide-y divide-gray-300">
                        <thead className="bg-gray-50">
                            <tr>
                                <th scope="col" className="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 sm:pl-6">
                                    Name
                                </th>
                                <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                                    Category
                                </th>
                                <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                                    Price
                                </th>
                                <th scope="col" className="relative py-3.5 pl-3 pr-4 sm:pr-6">
                                    <span className="sr-only">Edit</span>
                                </th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200 bg-white">
                          {people.map((person) => (
                            <tr key={person.id}>
                              <td className="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6">
                                {person.name}
                              </td>
                              <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                                {person.title}
                              </td>
                              <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                                {person.price}
                              </td>
                              <td className="relative whitespace-nowrap py-4 pl-3 pr-4 text-right text-sm font-medium sm:pr-6">
                                <button onClick={() => handleEdit(person)} className="text-indigo-600 hover:text-indigo-900">
                                  Edit<span className="sr-only">, {person.name}</span>
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
      </div>
      <div className="pointer-events-none fixed inset-x-0 bottom-0 sm:px-6 sm:pb-5 lg:px-8">
        <div className="pointer-events-auto flex items-center justify-between gap-x-6 bg-gray-900 px-6 py-2.5 sm:rounded-xl sm:py-3 sm:pl-4 sm:pr-3.5">
          <p className="text-sm leading-6 text-white">
            <a href="#">
              <strong className="font-semibold">Bolster</strong>
              <svg viewBox="0 0 2 2" className="mx-2 inline h-0.5 w-0.5 fill-current" aria-hidden="true">
                <circle cx={1} cy={1} r={1} />
              </svg>&nbsp;Demo
            </a>
          </p>
        </div>
      </div>
      {open && <EditModal person={selectedPerson} setOpen={setOpen} updatePerson={updatePerson} />}
    </div>
  );
}

function EditModal({ person, setOpen, updatePerson }) {
  const [name, setName] = useState(person.name);

  const handleSave = async () => {
    try {
      const response = await fetch('http://localhost:8000/categorizer/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text: name })
      });

      if (!response.ok) throw new Error('Network response was not ok.');

      const data = await response.json();
      // Assume that the response includes a 'category' and 'price'
      updatePerson(person.id, name, data.category, data.price); // Pass the new price along with the name and category
    } catch (error) {
      console.error("Error updating category:", error);
    } finally {
      setOpen(false);
    }
  };

  return (
    <Transition appear show as={Fragment}>
      <Dialog as="div" className="relative z-10" onClose={() => setOpen(false)}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-gray-500 bg-opacity-75" />
        </Transition.Child>
        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4 text-center">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-2xl bg-white p-6 text-left align-middle shadow-xl transition-all">
                <Dialog.Title as="h3" className="text-lg font-medium leading-6 text-gray-900">Edit Name</Dialog.Title>
                <input
                  type="text"
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
                <div className="mt-4">
                  <button
                    type="button"
                    className="inline-flex justify-center rounded-md border border-transparent bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2"
                    onClick={handleSave}
                  >
                    Save
                  </button>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}